from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, Ben2ImageBackgroundRemovalModelActionConfig
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import ImageBackgroundRemovalTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from ....utils.onnxruntime import resolve_onnx_providers
from PIL import Image as PILImage

if TYPE_CHECKING:
    import numpy as np
    import onnxruntime as ort

_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD  = (0.229, 0.224, 0.225)

class Ben2ImageBackgroundRemovalTaskAction(ImageBackgroundRemovalTaskAction):
    config: Ben2ImageBackgroundRemovalModelActionConfig

    def __init__(self, config: Ben2ImageBackgroundRemovalModelActionConfig, session: ort.InferenceSession):
        super().__init__(config, device=None)

        self.session: ort.InferenceSession = session

        self._input_name: str       = session.get_inputs()[0].name
        self._output_name: str      = session.get_outputs()[0].name
        self._input_size: int       = self._resolve_input_size(session)
        self._input_dtype: np.dtype = self._resolve_input_dtype(session)

    async def _predict_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _predict() -> List[PILImage.Image]:
            import numpy as np

            results: List[PILImage.Image] = []

            for image in images:
                image = image.convert("RGB")
                alpha = self.session.run([ self._output_name ], { self._input_name: self._preprocess(image) })[0]
                alpha = np.asarray(alpha, dtype=np.float32)

                if alpha.ndim != 4 or alpha.shape[:2] != (1, 1) or not np.isfinite(alpha).all():
                    raise RuntimeError("BEN2 returned an invalid alpha mask")

                # BEN2's logits aren't bounded to [0,1]; rescale via min/max so the
                # darkest pixel becomes 0 and the brightest 1. Guard against a
                # zero-range output by widening the denominator with eps.
                alpha = alpha[0, 0]
                minimum = float(alpha.min())
                span = max(float(alpha.max()) - minimum, float(np.finfo(np.float32).eps))
                mask = (np.clip((alpha - minimum) / span, 0.0, 1.0) * 255.0).astype(np.uint8)
                mask = PILImage.fromarray(mask, mode="L")

                results.append(self._render_output(image, mask, params["format"]))

            return results

        return await self._run_in_executor(_predict)

    def _preprocess(self, image: PILImage.Image) -> Any:
        import numpy as np

        resized = image.resize((self._input_size, self._input_size), PILImage.Resampling.LANCZOS)
        array = np.asarray(resized, dtype=np.float32) / 255.0
        array = (array - np.array(_IMAGENET_MEAN, dtype=np.float32)) / np.array(_IMAGENET_STD, dtype=np.float32)

        return np.ascontiguousarray(array.transpose(2, 0, 1)[None]).astype(self._input_dtype)

    @staticmethod
    def _resolve_input_size(session: ort.InferenceSession) -> int:
        # BEN2's ONNX export fixes a square input (1024 for the published export).
        shape = session.get_inputs()[0].shape

        if len(shape) != 4 or not isinstance(shape[2], int) or shape[2] <= 0 or shape[2] != shape[3]:
            raise RuntimeError(f"BEN2 ONNX export must have a static square NCHW input, got {shape}")

        return shape[2]

    @staticmethod
    def _resolve_input_dtype(session: ort.InferenceSession) -> np.dtype:
        # BEN2's published export uses fp16; pick the dtype up from the graph so
        # a user-provided fp32 export would also work without re-casting.
        import numpy as np

        input_type = session.get_inputs()[0].type

        if "float16" in input_type:
            return np.float16

        return np.float32

class Ben2ImageBackgroundRemovalTaskDriver(ModelTaskDriver):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.session: Optional[ort.InferenceSession] = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [
            ("onnxruntime", get_onnxruntime_distributions()),
            "numpy",
        ]

    async def _load_model(self) -> None:
        self.session = await self._load_onnx_session()

    async def _unload_model(self) -> None:
        self.session = None

    async def _load_onnx_session(self) -> ort.InferenceSession:
        import onnxruntime as ort

        model_path = await self._provision_model(self.config.model, prefetch=True)
        device = self._resolve_device(self.config.device, use_torch=False)

        def _load() -> ort.InferenceSession:
            providers = resolve_onnx_providers(device)

            logging.debug(f"BEN2 ONNX providers: {providers}")

            return ort.InferenceSession(model_path, providers=providers)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await Ben2ImageBackgroundRemovalTaskAction(action, self.session).run(context)
