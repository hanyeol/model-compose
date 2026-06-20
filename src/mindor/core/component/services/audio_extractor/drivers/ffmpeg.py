from __future__ import annotations

from typing import Optional, Dict, Set, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioExtractorComponentConfig
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.utils.streaming.audio import AudioStreamResource
from mindor.core.utils.streaming.media import MediaSource
from mindor.core.utils.streaming.stream import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.utils.streaming.file import FileStreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import AudioExtractorService, AudioExtractorDriver, register_audio_extractor_service
from ..base import ComponentActionContext
from .common import AudioExtractorAction
import asyncio, os

_FORMAT_CODEC_MAP: Dict[str, str] = {
    "mp3":  "libmp3lame",
    "wav":  "pcm_s16le",
    "flac": "flac",
    "aac":  "aac",
    "m4a":  "aac",
    "opus": "libopus",
    "ogg":  "libvorbis",
}

# Container formats safe to feed through ffmpeg pipe:0. Other formats (mp4/mov/mkv/webm/avi/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mp3", "wav", "flac", "ogg", "opus", "aac",
}

# Output container formats that can be written to ffmpeg's stdout (no post-write seek).
# Others (m4a/mp4-wrapped/...) need a real file path with seeking for moov atom placement
# or other container fix-ups.
_STREAMABLE_OUTPUT_FORMATS: Set[str] = {
    "mp3", "wav", "flac", "ogg", "opus", "aac",
}

class FFmpegAudioExtractorAction(AudioExtractorAction):
    async def _extract(
        self,
        source: MediaSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        track: Optional[int],
        loop: asyncio.AbstractEventLoop,
    ) -> AudioStreamResource:
        input_path, spooled = await self._resolve_input_path(source)
        is_streamable_output = format.lower() in _STREAMABLE_OUTPUT_FORMATS

        codec = codec or _FORMAT_CODEC_MAP.get(format)

        command = [ "ffmpeg", "-hide_banner" ]
        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-vn" ])

        if track is not None:
            command.extend([ "-map", f"0:a:{track}" ])
        if codec:
            command.extend([ "-c:a", codec ])
        if bitrate:
            command.extend([ "-b:a", bitrate ])

        def _cleanup() -> None:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(
            f"Extracting audio to '{format}' format "
            f"({'path' if input_path else 'pipe'} input, "
            f"{'stream' if is_streamable_output else 'file'} output)"
        )

        if is_streamable_output:
            return await self._extract_to_stream(command, source, input_path, format, _cleanup)

        return await self._extract_to_file(command, source, input_path, format, _cleanup)

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before extraction")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    async def _extract_to_file(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
        format: str,
        cleanup: Callable[[], None],
    ) -> AudioStreamResource:
        """Run ffmpeg to a temporary file, then return an AudioStreamResource over that file."""
        output_path = create_temporary_file(format)
        command = command + [ "-y", output_path ]

        try:
            process, _, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stderr_handler=lambda r: r.read(),
            )

            if process.returncode != 0:
                error = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg audio extraction failed (exit code {process.returncode}): {error}")
        finally:
            cleanup()

        logging.debug(f"Audio extraction completed: '{output_path}'")

        return AudioStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _extract_to_stream(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
        format: str,
        cleanup: Callable[[], None],
    ) -> AudioStreamResource:
        """Run ffmpeg writing to stdout and wrap the byte stream as an AudioStreamResource."""
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
                    raise RuntimeError(f"ffmpeg audio extraction failed (exit code {process.returncode}): {error_text}")
            finally:
                cleanup()

        return AudioStreamResource(AsyncIterableStreamResource(_stream()), format=format)

@register_audio_extractor_service(AudioExtractorDriver.FFMPEG)
class FFmpegAudioExtractorService(AudioExtractorService):
    def __init__(self, id: str, config: AudioExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioExtractorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegAudioExtractorAction(action).run(context, loop)
