from __future__ import annotations

from typing import Optional, Dict, Any
from mindor.dsl.schema.component import ImageCompressorComponentConfig
from mindor.dsl.schema.action import ImageCompressorActionConfig
from mindor.core.utils.shell import run_command
from ..base import ImageCompressorService, ImageCompressorDriver, register_image_compressor_service
from ..base import ComponentActionContext
from .common import ImageCompressorAction
from PIL import Image as PILImage
import shutil

class PngquantImageCompressorAction(ImageCompressorAction):
    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {
            "strip_metadata": await context.render_scalar(self.config.strip_metadata, bool),
            "speed":          await context.render_scalar(self.config.speed, int),
            "min_quality":    await context.render_scalar(self.config.min_quality, int),
            "max_quality":    await context.render_scalar(self.config.max_quality, int),
        }

    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        program = shutil.which("pngquant")

        if not program:
            raise RuntimeError("Image compressor driver 'pngquant' requires the 'pngquant' program in PATH.")

        input_png = await self._run_in_executor(self._encode_png_lossless, image, 6, False)
        command = [ program, "--speed", str(params["speed"]) ]

        if params["strip_metadata"]:
            command.append("--strip")

        quality = self._format_quality_range(params["min_quality"], params["max_quality"])

        if quality:
            command += [ "--quality", quality ]

        command += [ "--output", "-", "-" ]

        stdout, stderr, returncode = await run_command(command, input=input_png)

        if returncode != 0:
            raise RuntimeError(f"pngquant failed (exit {returncode}): {stderr.decode(errors='replace').strip()}")

        return stdout

    @staticmethod
    def _format_quality_range(min_quality: Optional[int], max_quality: Optional[int]) -> Optional[str]:
        if min_quality is None and max_quality is None:
            return None

        return f"{min_quality if min_quality is not None else 0}-{max_quality if max_quality is not None else 100}"

@register_image_compressor_service(ImageCompressorDriver.PNGQUANT)
class PngquantImageCompressorService(ImageCompressorService):
    def __init__(self, id: str, config: ImageCompressorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        return await PngquantImageCompressorAction(action).run(context)
