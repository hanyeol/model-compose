from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
import asyncio
import tempfile
import os

class FFmpegVideoConverterAction:
    def __init__(self, config: VideoConverterActionConfig):
        self.config: VideoConverterActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video       = await context.render_file(self.config.video)
        format      = await context.render_variable(self.config.format) if self.config.format else "mp4"
        codec       = await context.render_variable(self.config.codec) if self.config.codec else None
        audio_codec = await context.render_variable(self.config.audio_codec) if self.config.audio_codec else None
        bitrate     = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        resolution  = await context.render_variable(self.config.resolution) if self.config.resolution else None
        fps         = await context.render_variable(self.config.fps) if self.config.fps else None

        output_path = await self._convert(video, format, codec, audio_codec, bitrate, resolution, fps)
        result = {
            "path": output_path,
            "format": format
        }
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _convert(
        self,
        video: str,
        format: str,
        codec: Optional[str],
        audio_codec: Optional[str],
        bitrate: Optional[str],
        resolution: Optional[str],
        fps: Optional[str]
    ) -> str:
        output_path = os.path.join(tempfile.gettempdir(), f"video_converter_{os.getpid()}_{id(self)}.{format}")

        command = [ "ffmpeg", "-hide_banner", "-i", video ]

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

        logging.info(f"Converting '{video}' to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg conversion failed (exit code {process.returncode}): {error_output}")

        logging.info(f"Conversion completed: '{output_path}'")

        return output_path

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
