from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioCaptureComponentConfig
from mindor.dsl.schema.action import AudioCaptureActionConfig, AudioCaptureSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.utils.audio import is_audio_only_format
from mindor.core.utils.shell import kill_process
from mindor.core.logger import logging
from ..base import AudioCaptureService, AudioCaptureDriver, register_audio_capture_service
from ..base import ComponentActionContext
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from .common import AudioCaptureAction
import asyncio, os, platform, shutil, time

_STREAM_END = object()
_CHUNK_QUEUE_SIZE = 32

_DEFAULT_AUDIO_FORMAT = "aac"
_DEFAULT_AUDIO_CODEC  = "aac"

class FFmpegAudioCaptureAction(AudioCaptureAction):
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        system = platform.system()
        capture_pts = time.monotonic()

        audio_format, audio_iterator = await self._start_audio_capture(system, params)
        audio_stream = AudioStreamResource(
            AsyncIterableStreamResource(audio_iterator),
            format=audio_format,
            attrs={ "capture_pts": capture_pts },
        )

        return {
            "audio":       audio_stream,
            "capture_pts": capture_pts,
        }

    async def _start_audio_capture(
        self,
        system: str,
        params: Dict[str, Any],
    ) -> Tuple[str, AsyncIterator[bytes]]:
        source      = params["source"]
        encoding    = params["encoding"]
        sample_rate = params["sample_rate"]
        channels    = params["channels"]

        audio_format  = self._resolve_audio_format(encoding)
        audio_codec   = self._resolve_audio_codec(encoding, audio_format)
        audio_bitrate = encoding.audio.bitrate if encoding and encoding.audio and encoding.audio.bitrate else None

        if system == "Darwin" and source == AudioCaptureSource.SYSTEM:
            return audio_format, await self._start_macos_system_audio(
                audio_format, audio_codec, audio_bitrate, sample_rate, channels, params["duration"]
            )

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]
        command.extend(self._build_audio_input_args(system, source, params["device"]))
        command.extend([ "-c:a", audio_codec, "-flush_packets", "1" ])

        if sample_rate is not None:
            command.extend([ "-ar", str(sample_rate) ])

        if channels is not None:
            command.extend([ "-ac", str(channels) ])

        if audio_bitrate:
            command.extend([ "-b:a", str(audio_bitrate) ])

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        command.extend([ "-f", self._audio_muxer(audio_format), "pipe:1" ])

        logging.debug("Starting ffmpeg audio capture: %s", " ".join(command))

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )

        queue: asyncio.Queue = asyncio.Queue(maxsize=_CHUNK_QUEUE_SIZE)

        async def _reader() -> None:
            try:
                while True:
                    chunk = await process.stdout.read(65536)
                    if not chunk:
                        break
                    await queue.put(chunk)
            finally:
                await queue.put(_STREAM_END)

        reader_task = asyncio.create_task(_reader())

        async def _iterator() -> AsyncIterator[bytes]:
            try:
                while True:
                    item = await queue.get()
                    if item is _STREAM_END:
                        break
                    yield item
            finally:
                await kill_process(process, timeout=2.0)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return audio_format, _iterator()

    def _build_audio_input_args(
        self,
        system: str,
        source: AudioCaptureSource,
        device: Optional[Any],
    ) -> List[str]:
        if system == "Darwin":
            # macOS system loopback is not reachable via avfoundation; it is
            # handled by _start_macos_system_audio. Only microphone lands here.
            if source == AudioCaptureSource.MICROPHONE:
                spec = f":{device}" if device is not None else ":default"
                return [ "-f", "avfoundation", "-i", spec ]

        if system == "Windows":
            if source == AudioCaptureSource.SYSTEM:
                # WASAPI loopback of the default render endpoint.
                dev = device if device is not None else "virtual-audio-capturer"
                return [ "-f", "dshow", "-i", f"audio={dev}" ]

            if source == AudioCaptureSource.MICROPHONE:
                dev = device if device is not None else "default"
                return [ "-f", "dshow", "-i", f"audio={dev}" ]

        if system == "Linux":
            if source == AudioCaptureSource.SYSTEM:
                dev = device if device is not None else "default.monitor"
                return [ "-f", "pulse", "-i", str(dev) ]

            if source == AudioCaptureSource.MICROPHONE:
                dev = device if device is not None else "default"
                return [ "-f", "pulse", "-i", str(dev) ]

        raise NotImplementedError(f"Audio source '{source.value}' is not supported on platform: {system}")

    async def _start_macos_system_audio(
        self,
        audio_format: str,
        audio_codec: str,
        audio_bitrate: Optional[int],
        sample_rate: Optional[int],
        channels: Optional[int],
        duration: Optional[float],
    ) -> AsyncIterator[bytes]:
        """Pipe audiotee PCM into ffmpeg to encode macOS system loopback."""
        audiotee_path = shutil.which("audiotee")

        if not audiotee_path:
            raise RuntimeError(
                "macOS system audio capture requires the 'audiotee' CLI on PATH "
                "(see https://github.com/makeusabrew/audiotee). Install it with 'brew install audiotee' "
                "or set source: microphone to fall back to the microphone."
            )

        # audiotee outputs 32-bit float little-endian, mono, at the tap device's
        # native sample rate (48 kHz on typical Macs). Pass matching flags so
        # ffmpeg doesn't have to guess.
        tap_sample_rate = 48000
        tap_channels = 1

        audiotee_command = [ audiotee_path, "--chunk-duration", "0.1" ]
        ffmpeg_command: List[str] = [
            "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning",
            "-f", "f32le",
            "-ar", str(tap_sample_rate),
            "-ac", str(tap_channels),
            "-i", "pipe:0",
            "-c:a", audio_codec,
        ]

        if sample_rate is not None:
            ffmpeg_command.extend([ "-ar", str(sample_rate) ])

        if channels is not None:
            ffmpeg_command.extend([ "-ac", str(channels) ])

        if audio_bitrate:
            ffmpeg_command.extend([ "-b:a", str(audio_bitrate) ])

        if duration is not None:
            ffmpeg_command.extend([ "-t", str(duration) ])

        ffmpeg_command.extend([ "-f", self._audio_muxer(audio_format), "pipe:1" ])

        logging.debug("Starting audiotee | ffmpeg pipeline for macOS system audio")

        pipe_read_fd, pipe_write_fd = os.pipe()

        try:
            audiotee_process = await asyncio.create_subprocess_exec(
                *audiotee_command,
                stdout=pipe_write_fd,
                stderr=asyncio.subprocess.DEVNULL,
            )
            ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=pipe_read_fd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        finally:
            os.close(pipe_read_fd)
            os.close(pipe_write_fd)

        queue: asyncio.Queue = asyncio.Queue(maxsize=_CHUNK_QUEUE_SIZE)

        async def _reader() -> None:
            try:
                while True:
                    chunk = await ffmpeg_process.stdout.read(65536)
                    if not chunk:
                        break
                    await queue.put(chunk)
            finally:
                await queue.put(_STREAM_END)

        reader_task = asyncio.create_task(_reader())

        async def _iterator() -> AsyncIterator[bytes]:
            try:
                while True:
                    item = await queue.get()
                    if item is _STREAM_END:
                        break
                    yield item
            finally:
                await kill_process(ffmpeg_process, timeout=2.0)
                await kill_process(audiotee_process, timeout=2.0)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return _iterator()

    @staticmethod
    def _resolve_audio_format(encoding: Optional[VideoAudioEncodingParams]) -> str:
        if encoding and encoding.format:
            format = encoding.format.lower()

            if is_audio_only_format(format):
                return format

            if format in ("mp4", "mov"):
                return "m4a"

            if format == "webm":
                return "ogg"

        return _DEFAULT_AUDIO_FORMAT

    @staticmethod
    def _resolve_audio_codec(encoding: Optional[VideoAudioEncodingParams], audio_format: str) -> str:
        if encoding and encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        if audio_format in ("ogg", "opus"):
            return "libopus"

        return _DEFAULT_AUDIO_CODEC

    @staticmethod
    def _audio_muxer(audio_format: str) -> str:
        if audio_format == "m4a":
            return "ipod"

        if audio_format == "aac":
            return "adts"

        return audio_format

@register_audio_capture_service(AudioCaptureDriver.FFMPEG)
class FFmpegAudioCaptureService(AudioCaptureService):
    def __init__(self, id: str, config: AudioCaptureComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: AudioCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegAudioCaptureAction(action).run(context)
