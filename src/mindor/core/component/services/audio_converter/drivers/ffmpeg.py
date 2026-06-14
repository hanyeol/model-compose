from __future__ import annotations

from typing import Optional, Union, Any
from mindor.dsl.schema.component import AudioConverterComponentConfig
from mindor.dsl.schema.action import AudioConverterActionConfig
from mindor.core.utils.audio import AudioStreamResource
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, StreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.logger import logging
from ..base import AudioConverterService, AudioConverterDriver, register_audio_converter_service
from ..base import ComponentActionContext
from .common import AudioConverterAction
import asyncio

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

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format:
            command.extend([ "-f", source.format ])
        if source.attrs.get("sample_rate"):
            command.extend([ "-ar", str(source.attrs["sample_rate"]) ])
        if source.attrs.get("channels"):
            command.extend([ "-ac", str(source.attrs["channels"]) ])

        command.extend([ "-i", "pipe:0" ])

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

        logging.debug(f"Converting audio stream to '{format}' format")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stderr = await self._pipe_stream(process, source.stream)

        if process.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"ffmpeg audio conversion failed (exit code {process.returncode}): {error}")

        logging.debug(f"Audio conversion completed: '{output_path}'")

        return AudioStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

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

@register_audio_converter_service(AudioConverterDriver.FFMPEG)
class FFmpegAudioConverterService(AudioConverterService):
    def __init__(self, id: str, config: AudioConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: AudioConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioConverterAction(action).run(context)
