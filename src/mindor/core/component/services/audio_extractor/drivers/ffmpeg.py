from __future__ import annotations

from typing import Optional, Dict, Set, Any
from mindor.dsl.schema.component import AudioExtractorComponentConfig
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, StreamResource, save_stream_to_temporary_file
from mindor.core.utils.files import create_temporary_file
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

class FFmpegAudioExtractorAction(AudioExtractorAction):
    async def _extract(
        self,
        source: MediaSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        track: Optional[int]
    ) -> AudioStreamResource:
        output_path = create_temporary_file(format)
        codec = codec or _FORMAT_CODEC_MAP.get(format)

        input_path, spooled = await self._resolve_input_path(source)

        command = [ "ffmpeg", "-hide_banner" ]
        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-vn" ])

        if track is not None:
            command.extend([ "-map", f"0:a:{track}" ])
        if codec:
            command.extend([ "-c:a", codec ])
        if bitrate:
            command.extend([ "-b:a", bitrate ])

        command.extend([ "-y", output_path ])

        logging.debug(f"Extracting audio to '{format}' format")

        try:
            if input_path is not None:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await process.communicate()
            else:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stderr = await self._pipe_stream(process, source.stream)

            if process.returncode != 0:
                error_output = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg audio extraction failed (exit code {process.returncode}): {error_output}")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(f"Audio extraction completed: '{output_path}'")

        return AudioStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _resolve_input_path(self, source: MediaSource) -> tuple[Optional[str], bool]:
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

    async def _pipe_stream(self, process: asyncio.subprocess.Process, source: StreamResource) -> bytes:
        async def _feed() -> None:
            try:
                async for chunk in source:
                    try:
                        process.stdin.write(chunk)
                        await process.stdin.drain()
                    except (BrokenPipeError, ConnectionResetError):
                        break
            finally:
                try:
                    process.stdin.close()
                except Exception:
                    pass
                await source.close()

        feeder = asyncio.create_task(_feed())
        try:
            stderr = await process.stderr.read()
            await process.wait()
        finally:
            await feeder

        return stderr

@register_audio_extractor_service(AudioExtractorDriver.FFMPEG)
class FFmpegAudioExtractorService(AudioExtractorService):
    def __init__(self, id: str, config: AudioExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioExtractorAction(action).run(context)
