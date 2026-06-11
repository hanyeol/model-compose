from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import AudioExtractorComponentConfig
from mindor.dsl.schema.action import AudioExtractorActionConfig
from mindor.core.logger import logging
from ..base import AudioExtractorService, AudioExtractorDriver, register_audio_extractor_service
from ..base import ComponentActionContext
import asyncio
import tempfile
import os

_FORMAT_CODEC_MAP: Dict[str, str] = {
    "mp3":  "libmp3lame",
    "wav":  "pcm_s16le",
    "flac": "flac",
    "aac":  "aac",
    "m4a":  "aac",
    "opus": "libopus",
    "ogg":  "libvorbis",
}

class FFmpegAudioExtractorAction:
    def __init__(self, config: AudioExtractorActionConfig):
        self.config: AudioExtractorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source  = await context.render_file(self.config.source)
        format  = await context.render_variable(self.config.format) if self.config.format else "mp3"
        codec   = await context.render_variable(self.config.codec) if self.config.codec else None
        bitrate = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        track   = int(await context.render_variable(self.config.track)) if self.config.track is not None else None

        output_path = await self._extract(source, format, codec, bitrate, track)
        result = {
            "path": output_path,
            "format": format
        }
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else result

    async def _extract(
        self,
        source: str,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        track: Optional[int]
    ) -> str:
        output_path = os.path.join(tempfile.gettempdir(), f"audio_extractor_{os.getpid()}_{id(self)}.{format}")

        command = [ "ffmpeg", "-hide_banner", "-i", source, "-vn" ]

        if track is not None:
            command.extend([ "-map", f"0:a:{track}" ])

        resolved_codec = codec or _FORMAT_CODEC_MAP.get(format)
        if resolved_codec:
            command.extend([ "-c:a", resolved_codec ])
        if bitrate:
            command.extend([ "-b:a", bitrate ])

        command.extend([ "-y", output_path ])

        logging.info(f"Extracting audio from '{source}' to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg audio extraction failed (exit code {process.returncode}): {error_output}")

        logging.info(f"Audio extraction completed: '{output_path}'")

        return output_path

@register_audio_extractor_service(AudioExtractorDriver.FFMPEG)
class FFmpegAudioExtractorService(AudioExtractorService):
    def __init__(self, id: str, config: AudioExtractorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioExtractorAction(action).run(context)
