from __future__ import annotations

from typing import Optional, Dict, Any
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import asyncio
import tempfile
import os

class FFmpegVideoConverterAction(VideoConverterAction):
    async def run(self, context: ComponentActionContext) -> Any:
        data, source_attrs = await self._render_video(context)
        format      = await context.render_variable(self.config.format) if self.config.format else "mp4"
        codec       = await context.render_variable(self.config.codec) if self.config.codec else None
        audio_codec = await context.render_variable(self.config.audio_codec) if self.config.audio_codec else None
        bitrate     = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        resolution  = await context.render_variable(self.config.resolution) if self.config.resolution else None
        fps         = await context.render_variable(self.config.fps) if self.config.fps else None

        output_path = await self._convert(data, source_attrs, format, codec, audio_codec, bitrate, resolution, fps)
        result = {
            "path": output_path,
            "format": format
        }
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _convert(
        self,
        data: Any,
        source_attrs: Dict[str, Any],
        format: str,
        codec: Optional[str],
        audio_codec: Optional[str],
        bitrate: Optional[str],
        resolution: Optional[str],
        fps: Optional[str]
    ) -> str:
        output_path = os.path.join(tempfile.gettempdir(), f"video_converter_{os.getpid()}_{id(self)}.{format}")

        is_path = isinstance(data, str) and not source_attrs
        input_path = data if is_path else None

        command = [ "ffmpeg", "-hide_banner" ]

        if source_attrs.get("format"):
            command.extend([ "-f", str(source_attrs["format"]) ])
        if source_attrs.get("resolution"):
            command.extend([ "-s", str(source_attrs["resolution"]) ])
        if source_attrs.get("fps"):
            command.extend([ "-r", str(source_attrs["fps"]) ])
        if source_attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source_attrs["pixel_format"]) ])

        command.extend([ "-i", input_path if is_path else "pipe:0" ])

        if codec:
            command.extend([ "-c:v", codec ])
        if audio_codec:
            command.extend([ "-c:a", audio_codec ])
        if bitrate:
            command.extend([ "-b:v", bitrate ])
        if resolution:
            command.extend([ "-s", resolution ])
        if fps:
            command.extend([ "-r", fps ])

        command.extend([ "-movflags", "+faststart", "-y", output_path ])

        logging.info(f"Converting '{input_path if is_path else 'pipe:0'}' to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if not is_path else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        raw = bytes(data) if isinstance(data, (bytes, bytearray)) else None
        _, stderr = await process.communicate(input=raw)

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg conversion failed (exit code {process.returncode}): {error}")

        logging.info(f"Conversion completed: '{output_path}'")

        return output_path

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
