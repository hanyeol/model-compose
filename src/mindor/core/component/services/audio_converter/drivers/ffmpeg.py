from __future__ import annotations

from typing import Optional, Set, Tuple, Union, Any
from mindor.dsl.schema.component import AudioConverterComponentConfig
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import AudioConverterService, AudioConverterDriver, register_audio_converter_service
from ..base import ComponentActionContext
from .common import AudioConverterAction
import os

_FORMAT_CODEC_MAP: dict[str, str] = {
    "mp3":  "libmp3lame",
    "wav":  "pcm_s16le",
    "flac": "flac",
    "aac":  "aac",
    "m4a":  "aac",
    "opus": "libopus",
    "ogg":  "libvorbis",
}

# Container formats safe to feed through ffmpeg pipe:0. Other formats (m4a/mp4-wrapped/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mp3", "wav", "flac", "ogg", "opus", "aac",
}

class FFmpegAudioConverterAction(AudioConverterAction):
    async def _convert(
        self,
        source: MediaSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        sample_rate: Optional[Union[int, str]],
        channels: Optional[Union[int, str]],
    ) -> AudioStreamResource:
        output_path = create_temporary_file(format)
        input_path, spooled = await self._resolve_input_path(source)

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])
        if source.attrs.get("sample_rate"):
            command.extend([ "-ar", str(source.attrs["sample_rate"]) ])
        if source.attrs.get("channels"):
            command.extend([ "-ac", str(source.attrs["channels"]) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])

        codec = codec or _FORMAT_CODEC_MAP.get(format)
        if codec:
            command.extend([ "-c:a", codec ])
        if bitrate:
            command.extend([ "-b:a", bitrate ])
        if sample_rate:
            command.extend([ "-ar", str(sample_rate) ])
        if channels:
            command.extend([ "-ac", str(channels) ])

        command.extend([ "-y", output_path ])

        logging.debug(f"Converting audio to '{format}' format ({'path' if input_path else 'pipe'} input)")

        try:
            process, _, stderr = await run_subprocess(
                command,
                source.stream if input_path is None else None,
                stderr_handler=lambda r: r.read(),
            )

            if process.returncode != 0:
                error = stderr.decode("utf-8", errors="replace")
                raise RuntimeError(f"ffmpeg audio conversion failed (exit code {process.returncode}): {error}")
        finally:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(f"Audio conversion completed: '{output_path}'")

        return AudioStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (m4a/mp4-wrapped/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before conversion")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

@register_audio_converter_service(AudioConverterDriver.FFMPEG)
class FFmpegAudioConverterService(AudioConverterService):
    def __init__(self, id: str, config: AudioConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioConverterAction(action).run(context)
