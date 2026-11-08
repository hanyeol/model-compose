from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Tuple, Optional, Dict, List, Any
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, HatImageUpscalingModelActionConfig
from mindor.core.foundation.package.onnxruntime import get_onnxruntime_distributions
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.logger import logging
from ..common import ImageUpscalingTaskAction
from ....base import ComponentActionContext, ModelTaskDriver
from ....utils.onnxruntime import resolve_onnx_providers
from PIL import Image as PILImage

if TYPE_CHECKING:
    import onnxruntime as ort

class HatImageUpscalingTaskAction(ImageUpscalingTaskAction):
    config: HatImageUpscalingModelActionConfig

    def __init__(self, config: HatImageUpscalingModelActionConfig, session: ort.InferenceSession):
        super().__init__(config, device=None)

        self.session: ort.InferenceSession = session

        self._input_name: str  = session.get_inputs()[0].name
        self._output_name: str = session.get_outputs()[0].name

        self._tile_size, self._scale = self._resolve_session_geometry(session)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        tile_pad_size = await context.render_scalar(self.config.params.tile_pad_size, int)

        if tile_pad_size < 0 or tile_pad_size * 2 >= self._tile_size:
            raise ValueError(
                f"'tile_pad_size' must be in [0, {self._tile_size // 2}) for this HAT export, "
                f"got {tile_pad_size}"
            )

        params.update({
            "tile_pad_size": tile_pad_size,
        })

        return params

    async def _upscale_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        def _upscale() -> List[PILImage.Image]:
            results: List[PILImage.Image] = []

            for image in images:
                results.append(self._upscale(image, params["tile_pad_size"], cancellation_token))

            return results

        return await self._run_in_executor(_upscale)

    def _upscale(
        self,
        image: PILImage.Image,
        tile_pad_size: int,
        cancellation_token: Optional[CancellationToken],
    ) -> PILImage.Image:
        import numpy as np

        source = np.asarray(image.convert("RGB"), dtype=np.uint8)
        height, width = source.shape[:2]
        core_size = self._tile_size - 2 * tile_pad_size

        source = np.pad(
            source,
            ((tile_pad_size, tile_pad_size + (-height) % core_size),
             (tile_pad_size, tile_pad_size + (-width) % core_size),
             (0, 0)),
            mode=("reflect" if height > 1 and width > 1 else "edge"),
        )

        output = np.empty((height * self._scale, width * self._scale, 3), dtype=np.uint8)
        border = tile_pad_size * self._scale

        for top in range(0, height, core_size):
            core_height = min(core_size, height - top)

            for left in range(0, width, core_size):
                core_width = min(core_size, width - left)

                if cancellation_token is not None and cancellation_token.is_cancelled():
                    raise RuntimeError("HAT upscaling cancelled")

                tile = source[top : top + self._tile_size, left : left + self._tile_size]
                tile = np.ascontiguousarray(tile.astype(np.float32).transpose(2, 0, 1)[None] / 255.0)
                tile = self.session.run([ self._output_name ], { self._input_name: tile })[0]

                if not np.isfinite(tile).all():
                    raise RuntimeError("HAT model returned non-finite pixels")

                tile = np.rint(np.clip(tile[0].transpose(1, 2, 0), 0.0, 1.0) * 255.0).astype(np.uint8)
                
                output[
                    top  * self._scale : top  * self._scale + core_height * self._scale,
                    left * self._scale : left * self._scale + core_width  * self._scale,
                ] = tile[
                    border : border + core_height * self._scale,
                    border : border + core_width  * self._scale,
                ]

        return PILImage.fromarray(output, mode="RGB")

    @staticmethod
    def _resolve_session_geometry(session: ort.InferenceSession) -> Tuple[int, int]:
        # HAT's ONNX export fixes both input and output spatial dims, so the
        # super-resolution factor is baked into the graph. Read it from the
        # session rather than hardcoding — different exports (x2/x4/x8) all work.
        input_shape  = session.get_inputs()[0].shape
        output_shape = session.get_outputs()[0].shape
        input_height  = input_shape[2]
        output_height = output_shape[2]

        if not isinstance(input_height, int) or not isinstance(output_height, int) or input_height <= 0:
            raise RuntimeError(
                f"HAT ONNX export must have static spatial dimensions, "
                f"got input={input_shape}, output={output_shape}"
            )

        return input_height, output_height // input_height

class HatImageUpscalingTaskDriver(ModelTaskDriver):
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

            logging.debug(f"HAT ONNX providers: {providers}")

            return ort.InferenceSession(model_path, providers=providers)

        return await self._run_in_executor(_load)

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await HatImageUpscalingTaskAction(action, self.session).run(context)
