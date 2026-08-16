from __future__ import annotations

from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ImageCompressorComponentConfig
from mindor.dsl.schema.action import ImageCompressorActionConfig
from ..base import ImageCompressorService, ImageCompressorDriver, register_image_compressor_service
from ..base import ComponentActionContext
from .common import ImageCompressorAction
from PIL import Image as PILImage

class OxipngImageCompressorAction(ImageCompressorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        strip_metadata = await context.render_scalar(self.config.strip_metadata, bool)
        level          = await context.render_scalar(self.config.level, int)

        return {
            "strip_metadata": strip_metadata,
            "level":          level,
        }

    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        def _compress() -> bytes:
            import oxipng

            # Encode losslessly first so oxipng has a valid PNG to optimize.
            # Preserve metadata at this stage; oxipng strips it below when requested.
            data = self._encode_png_lossless(image, compress_level=6, strip_metadata=False)

            if params["strip_metadata"]:
                strip = oxipng.StripChunks.safe()
            else:
                strip = oxipng.StripChunks.none()

            return oxipng.optimize_from_memory(data, level=params["level"], strip=strip)

        return await self._run_in_executor(_compress)

@register_image_compressor_service(ImageCompressorDriver.OXIPNG)
class OxipngImageCompressorService(ImageCompressorService):
    def __init__(self, id: str, config: ImageCompressorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "pyoxipng" ]

    async def _run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        return await OxipngImageCompressorAction(action).run(context)
