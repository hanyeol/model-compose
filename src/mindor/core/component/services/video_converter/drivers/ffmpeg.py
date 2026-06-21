from __future__ import annotations

from typing import Optional, Set, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig, VideoAudioCodecConfig
from mindor.core.utils.streaming.video import VideoStreamResource
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.utils.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import asyncio, os

# Container formats safe to feed through ffmpeg pipe:0. Other formats (mp4/mov/mkv/avi/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

# Output container formats that can be written to ffmpeg's stdout (no post-write seek).
# Others (mp4/mov/mkv/avi/...) need a real file path with seeking — typically for moov atom
# placement, index tables, +faststart, etc.
_STREAMABLE_OUTPUT_FORMATS: Set[str] = {
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
        fps: Optional[str],
        loop: asyncio.AbstractEventLoop,
    ) -> VideoStreamResource:
        input_path, spooled = await self._resolve_input_path(source)
        is_streamable_output = format.lower() in _STREAMABLE_OUTPUT_FORMATS

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

        def _cleanup() -> None:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(
            f"Converting video to '{format}' format "
            f"({'path' if input_path else 'pipe'} input, "
            f"{'stream' if is_streamable_output else 'file'} output)"
        )

        if is_streamable_output:
            return await self._convert_to_stream(command, source, input_path, format, _cleanup)

        return await self._convert_to_file(command, source, input_path, format, _cleanup)

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

    async def _convert_to_file(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
        format: str,
        cleanup: Callable[[], None],
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = create_temporary_file(format)

        command = command + [ "-movflags", "+faststart", "-y", output_path ]

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
            cleanup()

        logging.debug(f"Video conversion completed: '{output_path}'")

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _convert_to_stream(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
        format: str,
        cleanup: Callable[[], None],
    ) -> VideoStreamResource:
        """Run ffmpeg writing to stdout and wrap the byte stream as a VideoStreamResource."""
        command = command + [ "-f", format, "pipe:1" ]
        error: list = []

        async def _handle_stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
            while True:
                chunk = await reader.read(65536)

                if not chunk:
                    break

                yield chunk

        async def _handle_stderr(reader: asyncio.StreamReader) -> None:
            while True:
                line = await reader.readline()

                if not line:
                    break

                error.append(line)

        async def _stream() -> AsyncIterator[bytes]:
            try:
                async with stream_subprocess(
                    command,
                    source=source.stream if input_path is None else None,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
                ) as (process, chunks, _):
                    async for chunk in chunks:
                        yield chunk

                if process.returncode is not None and process.returncode != 0:
                    error_text = b"".join(error).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ffmpeg video conversion failed (exit code {process.returncode}): {error_text}")
            finally:
                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoConverterAction(action).run(context, loop)
