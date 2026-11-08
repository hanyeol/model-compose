from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, BiRefNetImageBackgroundRemovalModelActionConfig
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import ImageBackgroundRemovalTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from ....utils.onnxruntime import resolve_onnx_providers
from PIL import Image as PILImage

if TYPE_CHECKING:
    import onnxruntime as ort

_IMAGENET_MEAN = (0.485, 0.456, 0.406)
_IMAGENET_STD  = (0.229, 0.224, 0.225)

class BiRefNetImageBackgroundRemovalTaskAction(ImageBackgroundRemovalTaskAction):
    config: BiRefNetImageBackgroundRemovalModelActionConfig

    def __init__(self, config: BiRefNetImageBackgroundRemovalModelActionConfig, session: ort.InferenceSession):
        super().__init__(config, device=None)

        self.session: ort.InferenceSession = session

        self._input_name: str  = session.get_inputs()[0].name
        self._output_name: str = session.get_outputs()[0].name
        self._input_size: int  = self._resolve_input_size(session)

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
                    raise RuntimeError("BiRefNet returned an invalid alpha logits tensor")

                # Published BiRefNet ONNX exports emit raw logits; apply sigmoid
                # to turn them into an alpha matte in [0, 1].
                alpha = 1.0 / (1.0 + np.exp(-alpha[0, 0]))
                mask = (np.clip(alpha, 0.0, 1.0) * 255.0).astype(np.uint8)
                mask = PILImage.fromarray(mask, mode="L")

                results.append(self._render_output(image, mask, params["format"]))

            return results

        return await self._run_in_executor(_predict)

    def _preprocess(self, image: PILImage.Image) -> Any:
        import numpy as np

        resized = image.resize((self._input_size, self._input_size), PILImage.Resampling.BILINEAR)
        array = np.asarray(resized, dtype=np.float32) / 255.0
        array = (array - np.array(_IMAGENET_MEAN, dtype=np.float32)) / np.array(_IMAGENET_STD, dtype=np.float32)

        return np.ascontiguousarray(array.transpose(2, 0, 1)[None])

    @staticmethod
    def _resolve_input_size(session: ort.InferenceSession) -> int:
        # BiRefNet's ONNX export fixes a square input (1024 for Lite, 2048 for
        # HR-matting). Read from the graph rather than hardcoding so both
        # exports work with the same driver.
        shape = session.get_inputs()[0].shape

        if len(shape) != 4 or not isinstance(shape[2], int) or shape[2] <= 0 or shape[2] != shape[3]:
            raise RuntimeError(f"BiRefNet ONNX export must have a static square NCHW input, got {shape}")

        return shape[2]

class BiRefNetImageBackgroundRemovalTaskDriver(ModelTaskDriver):
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

            logging.debug(f"BiRefNet ONNX providers: {providers}")

            return ort.InferenceSession(model_path, providers=providers)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await BiRefNetImageBackgroundRemovalTaskAction(action, self.session).run(context)
