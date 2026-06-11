from __future__ import annotations

from typing import Optional, Tuple, Any
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoAudioCodecConfig
from mindor.core.utils.video import VideoStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, StreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import asyncio

_FORMAT_CODEC_MAP: dict[str, tuple[str, str]] = {
    "mp4":  ("libx264",    "aac"),
    "m4v":  ("libx264",    "aac"),
    "mov":  ("libx264",    "aac"),
    "mkv":  ("libx264",    "aac"),
    "webm": ("libvpx-vp9", "libopus"),
    "avi":  ("mpeg4",      "libmp3lame"),
    "ogv":  ("libtheora",  "libvorbis"),
}

class FFmpegVideoConverterAction(VideoConverterAction):
    async def run(self, context: ComponentActionContext) -> Any:
        source     = await context.render_video(self.config.video)
        format     = await context.render_variable(self.config.format) if self.config.format else "mp4"
        video_codec, audio_codec = await self._resolve_codec(context, format)
        bitrate    = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        resolution = await context.render_variable(self.config.resolution) if self.config.resolution else None
        fps        = await context.render_variable(self.config.fps) if self.config.fps else None

        result = await self._convert(source, format, video_codec, audio_codec, bitrate, resolution, fps)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _convert(
        self,
        source: MediaSource,
        format: str,
        video_codec: Optional[str],
        audio_codec: Optional[str],
        bitrate: Optional[str],
        resolution: Optional[str],
        fps: Optional[str]
    ) -> VideoStreamResource:
        output_path = create_temporary_file(format)

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format:
            command.extend([ "-f", source.format ])
        if source.attrs.get("resolution"):
            command.extend([ "-s", str(source.attrs["resolution"]) ])
        if source.attrs.get("fps"):
            command.extend([ "-r", str(source.attrs["fps"]) ])
        if source.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source.attrs["pixel_format"]) ])

        command.extend([ "-i", "pipe:0" ])

        if video_codec:
            command.extend([ "-c:v", video_codec ])
        if audio_codec:
            command.extend([ "-c:a", audio_codec ])
        if bitrate:
            command.extend([ "-b:v", bitrate ])
        if resolution:
            command.extend([ "-s", resolution ])
        if fps:
            command.extend([ "-r", fps ])

        command.extend([ "-movflags", "+faststart", "-y", output_path ])

        logging.debug(f"Converting video stream to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stderr = await self._pipe_stream(process, source.stream)

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg video conversion failed (exit code {process.returncode}): {error}")

        logging.debug(f"Video conversion completed: '{output_path}'")

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _resolve_codec(self, context: ComponentActionContext, format: str) -> Tuple[Optional[str], Optional[str]]:
        default_video_codec, default_audio_codec = _FORMAT_CODEC_MAP.get(format, (None, None))

        if isinstance(self.config.codec, VideoAudioCodecConfig):
            video_codec = await context.render_variable(self.config.codec.video) if self.config.codec.video else default_video_codec
            audio_codec = await context.render_variable(self.config.codec.audio) if self.config.codec.audio else default_audio_codec
        elif self.config.codec:
            video_codec = await context.render_variable(self.config.codec)
            audio_codec = default_audio_codec
        else:
            video_codec = default_video_codec
            audio_codec = default_audio_codec

        return video_codec, audio_codec

    async def _pipe_stream(self, process: asyncio.subprocess.Process, source: StreamResource) -> bytes:
        async def _feed() -> None:
            try:
                async for chunk in source:
                    process.stdin.write(chunk)
                    await process.stdin.drain()
            finally:
                process.stdin.close()
                await source.close()

        feeder = asyncio.create_task(_feed())
        try:
            stderr = await process.stderr.read()
            await process.wait()
        finally:
            await feeder

        return stderr

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
