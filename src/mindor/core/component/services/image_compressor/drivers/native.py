from __future__ import annotations

from typing import Dict, Any
from mindor.dsl.schema.component import ImageCompressorComponentConfig
from mindor.dsl.schema.action import ImageCompressorActionConfig
from ..base import ImageCompressorService, ImageCompressorDriver, register_image_compressor_service
from ..base import ComponentActionContext
from .common import ImageCompressorAction
from PIL import Image as PILImage

class NativeImageCompressorAction(ImageCompressorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        strip_metadata = await context.render_scalar(self.config.strip_metadata, bool)
        compress_level = await context.render_scalar(self.config.compress_level, int)

        return {
            "strip_metadata": strip_metadata,
            "compress_level": compress_level,
        }

    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        def _compress() -> bytes:
            return self._encode_png_lossless(image, params["compress_level"], params["strip_metadata"])

        return await self._run_in_executor(_compress)

@register_image_compressor_service(ImageCompressorDriver.NATIVE)
class NativeImageCompressorService(ImageCompressorService):
    def __init__(self, id: str, config: ImageCompressorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeImageCompressorAction(action).run(context)
