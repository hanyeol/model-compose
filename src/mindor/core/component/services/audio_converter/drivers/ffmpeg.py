from __future__ import annotations

from typing import Optional, Union, Any
from mindor.dsl.schema.component import AudioConverterComponentConfig
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.logger import logging
from ..base import AudioConverterService, AudioConverterDriver, register_audio_converter_service
from ..base import ComponentActionContext
from .common import AudioConverterAction, AudioSource
import asyncio
import tempfile
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

class FFmpegAudioConverterAction(AudioConverterAction):
    async def run(self, context: ComponentActionContext) -> Any:
        source      = await self._render_source(context)
        format      = await context.render_variable(self.config.format) if self.config.format else "wav"
        codec       = await context.render_variable(self.config.codec) if self.config.codec else None
        bitrate     = await context.render_variable(self.config.bitrate) if self.config.bitrate else None
        sample_rate = await context.render_variable(self.config.sample_rate) if isinstance(self.config.sample_rate, str) else self.config.sample_rate
        channels    = await context.render_variable(self.config.channels) if isinstance(self.config.channels, str) else self.config.channels

        output_path = await self._convert(source, format, codec, bitrate, sample_rate, channels)
        result = {
            "path": output_path,
            "format": format
        }
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _convert(
        self,
        source: AudioSource,
        format: str,
        codec: Optional[str],
        bitrate: Optional[str],
        sample_rate: Optional[Union[int, str]],
        channels: Optional[Union[int, str]],
    ) -> str:
        output_path = os.path.join(tempfile.gettempdir(), f"audio_converter_{os.getpid()}_{id(self)}.{format}")

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format:
            command.extend([ "-f", source.format ])
        if source.sample_rate:
            command.extend([ "-ar", str(source.sample_rate) ])
        if source.channels:
            command.extend([ "-ac", str(source.channels) ])

        is_pipe = source.data is not None
        command.extend([ "-i", "pipe:0" if is_pipe else source.path ])

        resolved_codec = codec or _FORMAT_CODEC_MAP.get(format)
        if resolved_codec:
            command.extend([ "-c:a", resolved_codec ])
        if bitrate:
            command.extend([ "-b:a", bitrate ])
        if sample_rate:
            command.extend([ "-ar", str(sample_rate) ])
        if channels:
            command.extend([ "-ac", str(channels) ])

        command.extend([ "-y", output_path ])

        logging.info(f"Converting '{'pipe:0' if is_pipe else source.path}' to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE if is_pipe else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        raw = bytes(source.data) if isinstance(source.data, (bytes, bytearray)) else None
        _, stderr = await process.communicate(input=raw)

        if process.returncode != 0:
            error_output = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg audio conversion failed (exit code {process.returncode}): {error_output}")

        logging.info(f"Audio conversion completed: '{output_path}'")

        return output_path

@register_audio_converter_service(AudioConverterDriver.FFMPEG)
class FFmpegAudioConverterService(AudioConverterService):
    def __init__(self, id: str, config: AudioConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioConverterAction(action).run(context)
