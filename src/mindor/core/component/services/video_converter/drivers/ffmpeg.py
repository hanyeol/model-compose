from __future__ import annotations

from typing import Optional, Set, Tuple, Any
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoAudioCodecConfig
from mindor.core.utils.video import VideoStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import os

# Container formats safe to feed through ffmpeg pipe:0. Other formats (mp4/mov/mkv/avi/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

class FFmpegVideoConverterAction(VideoConverterAction):
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
        input_path, spooled = await self._resolve_input_path(source)

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])
        if source.attrs.get("resolution"):
            command.extend([ "-s", str(source.attrs["resolution"]) ])
        if source.attrs.get("fps"):
            command.extend([ "-r", str(source.attrs["fps"]) ])
        if source.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source.attrs["pixel_format"]) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])

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

        logging.debug(f"Converting video to '{format}' format ({'path' if input_path else 'pipe'} input)")

        try:
            process, _, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stderr_handler=lambda r: r.read(),
            )

            if process.returncode != 0:
                error = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg video conversion failed (exit code {process.returncode}): {error}")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(f"Video conversion completed: '{output_path}'")

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mpegts, webm, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/mkv/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before conversion")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
