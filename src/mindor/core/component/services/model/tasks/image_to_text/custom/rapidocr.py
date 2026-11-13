from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, RapidOcrImageToTextModelComponentConfig, RapidOcrModel
from mindor.dsl.schema.action import ModelActionConfig, RapidOcrImageToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.logger import logging
from ..common import ImageToTextTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from ....utils.onnxruntime import ProviderSpec, resolve_onnx_providers
from PIL import Image as PILImage

if TYPE_CHECKING:
    from rapidocr import RapidOCR

# RapidOCR model variant → (PP-OCR version, model size). Kept as plain strings
# so the module can be imported without the rapidocr package installed; the
# driver resolves them to RapidOCR's OCRVersion / ModelType enums at load time.
_RAPIDOCR_MODEL_VARIANTS: Dict[RapidOcrModel, Tuple[str, str]] = {
    RapidOcrModel.V6_SMALL:  ("PP-OCRv6", "small"),
    RapidOcrModel.V6_TINY:   ("PP-OCRv6", "tiny"),
    RapidOcrModel.V6_MEDIUM: ("PP-OCRv6", "medium"),
    RapidOcrModel.V5_MOBILE: ("PP-OCRv5", "mobile"),
    RapidOcrModel.V5_SERVER: ("PP-OCRv5", "server"),
    RapidOcrModel.V4_MOBILE: ("PP-OCRv4", "mobile"),
    RapidOcrModel.V4_SERVER: ("PP-OCRv4", "server"),
}

# ISO 639-1 / BCP 47 → RapidOCR (det_lang, rec_lang) per PP-OCR version.
# Only lists combinations RapidOCR actually ships; unsupported pairs raise.
# Det uses the version's native coverage ('multi' where available), Rec uses
# the matching per-language recognizer.
_RAPIDOCR_LANGUAGE_CODE_MAP: Dict[RapidOcrModel, Dict[str, Tuple[str, str]]] = {
    # PP-OCRv6 only ships 'multi' det/rec in three sizes; it covers en/zh.
    RapidOcrModel.V6_SMALL: {
        "en":    ("en", "en"),
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
    },
    RapidOcrModel.V6_TINY: {
        "en":    ("en", "en"),
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
    },
    RapidOcrModel.V6_MEDIUM: {
        "en":    ("en", "en"),
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
    },
    # v5 mobile has per-language rec (en, korean, ...); v5 server only has
    # Chinese rec/det. v5 ships no non-Chinese det models, so Latin-script
    # languages piggyback on the Chinese detector (works well enough).
    RapidOcrModel.V5_MOBILE: {
        "en":    ("ch", "en"),
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
        "ko":    ("ch", "korean"),
    },
    RapidOcrModel.V5_SERVER: {
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
    },
    # v4 ships per-language rec (en/japan/korean/...) only in mobile size;
    # server only has Chinese. v4 does have a dedicated multi-language det.
    RapidOcrModel.V4_MOBILE: {
        "en":    ("en", "en"),
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
        "ja":    ("multi", "japan"),
        "ko":    ("multi", "korean"),
    },
    RapidOcrModel.V4_SERVER: {
        "zh":    ("ch", "ch"),
        "zh-CN": ("ch", "ch"),
    },
}

class RapidOcrImageToTextTaskAction(ImageToTextTaskAction):
    config: RapidOcrImageToTextModelActionConfig

    def __init__(self, config: RapidOcrImageToTextModelActionConfig, engine: RapidOCR):
        super().__init__(config)

        self.engine: RapidOCR = engine

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        return_polygons = await context.render_scalar(self.config.return_polygons, bool)
        text_score      = await context.render_scalar(self.config.params.text_score, float)
        box_thresh      = await context.render_scalar(self.config.params.box_thresh, float)
        unclip_ratio    = await context.render_scalar(self.config.params.unclip_ratio, float)
        use_cls         = await context.render_scalar(self.config.params.use_cls, bool)

        params.update({
            "return_polygons": return_polygons,
            "text_score":      text_score,
            "box_thresh":      box_thresh,
            "unclip_ratio":    unclip_ratio,
            "use_cls":         use_cls,
        })

        return params

    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        prompts: Optional[List[str]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Union[str, Dict[str, Any]]]]:
        return_polygons = params["return_polygons"]

        def _recognize() -> List[List[Union[str, Dict[str, Any]]]]:
            import numpy as np

            results: List[List[Union[str, Dict[str, Any]]]] = []

            for image in images:
                rgb = np.asarray(image.convert("RGB"))
                height, width = rgb.shape[:2]

                result = self.engine(
                    rgb,
                    use_cls=params["use_cls"],
                    text_score=params["text_score"],
                    box_thresh=params["box_thresh"],
                    unclip_ratio=params["unclip_ratio"],
                )

                results.append([ self._build_result(result, width, height, return_polygons) ])

            return results

        return await self._run_in_executor(_recognize)

    def _build_result(self, result: Any, width: int, height: int, return_polygons: bool) -> Union[str, Dict[str, Any]]:
        # Use explicit None checks: RapidOCR returns numpy arrays for `boxes`
        # (and sometimes `scores`), and `or []` would evaluate their truthiness
        # ambiguously.
        boxes  = result.boxes  if getattr(result, "boxes",  None) is not None else []
        txts   = result.txts   if getattr(result, "txts",   None) is not None else []
        scores = result.scores if getattr(result, "scores", None) is not None else []

        if not return_polygons:
            return "\n".join(txts)

        polygons: List[Dict[str, Any]] = []

        for box, text, score in zip(boxes, txts, scores):
            polygons.append({
                "text":    text,
                "polygon": [ { "x": int(point[0]), "y": int(point[1]) } for point in box ],
                "score":   float(score),
            })

        return {
            "text":     "\n".join(txts),
            "polygons": polygons,
            "width":    width,
            "height":   height,
        }

class RapidOcrImageToTextTaskDriver(ModelTaskDriver):
    config: RapidOcrImageToTextModelComponentConfig

    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.engine: Optional[RapidOCR] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            ("onnxruntime", get_onnxruntime_distributions()),
            "rapidocr",
            "opencv-python",
        ]

    async def _load_model(self) -> None:
        self.engine = await self._load_engine()

    async def _unload_model(self) -> None:
        self.engine = None

    async def _load_engine(self) -> RapidOCR:
        device = self._resolve_device(self.config.device, use_torch=False)

        def _load() -> RapidOCR:
            from rapidocr import RapidOCR

            providers = resolve_onnx_providers(device)

            logging.debug(f"RapidOCR ONNX providers: {providers}")

            engine_params = self._build_engine_params(
                RapidOcrModel(self.config.model.name),
                providers,
                self.config.language
            )

            return RapidOCR(params=engine_params)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await RapidOcrImageToTextTaskAction(action, self.engine).run(context)

    def _build_engine_params(self, model: RapidOcrModel, providers: List[ProviderSpec], language: Optional[str]) -> Dict[str, Any]:
        from rapidocr.utils.typings import ModelType, OCRVersion

        model_version, model_size = _RAPIDOCR_MODEL_VARIANTS[model]
        ocr_version, model_type = OCRVersion(model_version), ModelType(model_size)
        det_lang, rec_lang = self._resolve_language(model, language)

        return {
            "Det.ocr_version": ocr_version,
            "Det.model_type":  model_type,
            "Det.lang_type":   det_lang,
            "Rec.ocr_version": ocr_version,
            "Rec.model_type":  model_type,
            "Rec.lang_type":   rec_lang,
            **self._build_engine_device_params(providers),
        }

    def _build_engine_device_params(self, providers: List[ProviderSpec]) -> Dict[str, Any]:
        # RapidOCR's Det/Cls/Rec submodels all read the same EngineConfig.onnxruntime
        # block, so one flag here switches all three submodels at once.
        primary = next((provider for provider in providers if provider != "CPUExecutionProvider"), None)

        if primary is None:
            return {}

        provider, options = primary if isinstance(primary, tuple) else (primary, {})
        params: Dict[str, Any] = {}

        if provider == "CUDAExecutionProvider":
            params["EngineConfig.onnxruntime.use_cuda"] = True
            params["EngineConfig.onnxruntime.cuda_ep_cfg.device_id"] = options.get("device_id", 0)
        elif provider == "CoreMLExecutionProvider":
            params["EngineConfig.onnxruntime.use_coreml"] = True
        elif provider == "DmlExecutionProvider":
            params["EngineConfig.onnxruntime.use_dml"] = True
        else:
            logging.warning(f"RapidOCR does not expose a flag for ONNX provider {provider!r}; falling back to CPU.")

        return params

    def _resolve_language(self, model: RapidOcrModel, language: Optional[str]) -> Tuple[str, str]:
        supported_languages = _RAPIDOCR_LANGUAGE_CODE_MAP[model]

        # Prefer 'en' as the implicit default; fall back to the first supported
        # language for model variants that don't carry an English recognizer
        # (e.g. v5-server / v4-server ship only Chinese).
        if not language:
            language = "en" if "en" in supported_languages else next(iter(supported_languages))

        if language not in supported_languages:
            supported = ", ".join(sorted(supported_languages.keys()))

            raise ValueError(
                f"RapidOCR model {model.value!r} does not support language {language!r}. "
                f"Supported languages for this model: {supported}."
            )

        return supported_languages[language]
