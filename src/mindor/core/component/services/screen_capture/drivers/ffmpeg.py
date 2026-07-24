from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ScreenCaptureComponentConfig
from mindor.dsl.schema.action import (
    ScreenCaptureActionConfig,
    ScreenCaptureVideoSource,
    ScreenCaptureAudioSource,
)
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.utils.shell import kill_process
from mindor.core.logger import logging
from ..base import ScreenCaptureService, ScreenCaptureDriver, register_screen_capture_service
from ..base import ComponentActionContext
from .common import ScreenCaptureAction, VideoAudioEncodingParams
import asyncio, os, platform, shutil, time

# Sentinel put on the chunk queue to signal end-of-stream to the consumer.
_STREAM_END = object()

# How many encoded chunks may sit in the queue before the reader task blocks.
# Encoded video chunks are ~KB-scale; 32 gives ~1s of buffering at typical bitrates.
_CHUNK_QUEUE_SIZE = 32

# MPEG-TS is the default video container because it is designed for streaming:
# each packet is self-contained, so encoded chunks are available immediately
# without waiting for an mp4 fragment to close. mp4 over a pipe has multi-second
# first-byte latency even with frag_keyframe. We surface it as "ts" so
# VideoStreamResource resolves to the "video/mp2t" content type.
_DEFAULT_VIDEO_FORMAT = "ts"
_DEFAULT_VIDEO_CODEC  = "libx264"
_DEFAULT_AUDIO_FORMAT = "aac"
_DEFAULT_AUDIO_CODEC  = "aac"

class FFmpegScreenCaptureAction(ScreenCaptureAction):
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        system = platform.system()
        capture_pts = time.monotonic()

        video_stream: Optional[VideoStreamResource] = None
        audio_stream: Optional[AudioStreamResource] = None

        if params["include_video"]:
            video_format, video_iterator = await self._start_video_capture(system, params)
            video_stream = VideoStreamResource(
                AsyncIterableStreamResource(video_iterator),
                format=video_format,
                attrs={ "capture_pts": capture_pts },
            )

        if params["include_audio"] and params["audio_source"] != ScreenCaptureAudioSource.NONE:
            audio_format, audio_iterator = await self._start_audio_capture(system, params)
            audio_stream = AudioStreamResource(
                AsyncIterableStreamResource(audio_iterator),
                format=audio_format,
                attrs={ "capture_pts": capture_pts },
            )

        return {
            "video":       video_stream,
            "audio":       audio_stream,
            "capture_pts": capture_pts,
        }

    async def _start_video_capture(
        self,
        system: str,
        params: Dict[str, Any],
    ) -> Tuple[str, AsyncIterator[bytes]]:
        """Spawn ffmpeg for the video track and return (format, chunk_iterator)."""
        video_source = params["video_source"]
        encoding     = params["encoding"]
        framerate    = params["framerate"]
        display      = params["display"]
        region       = params.get("region")

        if video_source not in (ScreenCaptureVideoSource.DISPLAY, ScreenCaptureVideoSource.REGION):
            # MVP covers display + region only. Window capture needs per-OS
            # lookups (window titles/IDs) that aren't wired up yet.
            raise NotImplementedError(f"screen-capture video_source '{video_source.value}' is not supported yet")

        video_format  = self._resolve_container_format(encoding)
        video_codec   = self._resolve_video_codec(encoding)
        video_bitrate = encoding.video.bitrate if encoding and encoding.video and encoding.video.bitrate else None

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]
        command.extend(self._build_video_input_args(system, display, framerate, region))
        command.extend([
            "-c:v", video_codec,
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-g", str(max(1, int(framerate))),
            "-pix_fmt", "yuv420p",
            "-flush_packets", "1",
        ])

        # macOS avfoundation can't crop at the input stage, so apply a crop
        # filter after decode. Windows gdigrab and Linux x11grab already
        # accept the region at input time (see _build_video_input_args).
        if region is not None and system == "Darwin":
            command.extend([ "-vf", f"crop={region['width']}:{region['height']}:{region['x']}:{region['y']}" ])

        if video_bitrate:
            command.extend([ "-b:v", str(video_bitrate) ])

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        command.extend([ "-f", self._container_muxer(video_format) ])

        if video_format in ("mp4", "mov", "m4v"):
            # Fragmented mp4 flags are required for pipe output; without them
            # ffmpeg tries to seek back to the header at close-time and errors.
            command.extend([ "-movflags", "frag_keyframe+empty_moov+default_base_moof" ])

        command.append("pipe:1")

        logging.debug("Starting ffmpeg video capture: %s", " ".join(command))

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
                await kill_process(process)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return video_format, _iterator()

    async def _start_audio_capture(
        self,
        system: str,
        params: Dict[str, Any],
    ) -> Tuple[str, AsyncIterator[bytes]]:
        """Spawn the audio backend and return (format, chunk_iterator).

        Sources fan out per-OS:
        - Linux/Windows: single ffmpeg process reads from the OS mixer.
        - macOS system loopback: audiotee (Core Audio process-tap) sidecar pipes
          PCM into an ffmpeg encoder, since ffmpeg on macOS cannot tap system
          output directly.
        - macOS microphone: ffmpeg avfoundation.
        """
        audio_source = params["audio_source"]
        encoding     = params["encoding"]

        audio_format  = self._resolve_audio_format(encoding)
        audio_codec   = self._resolve_audio_codec(encoding, audio_format)
        audio_bitrate = encoding.audio.bitrate if encoding and encoding.audio and encoding.audio.bitrate else None

        if system == "Darwin" and audio_source == ScreenCaptureAudioSource.SYSTEM:
            return audio_format, await self._start_macos_system_audio(
                audio_format, audio_codec, audio_bitrate, params["duration"]
            )

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]
        command.extend(self._build_audio_input_args(system, audio_source))
        command.extend([ "-c:a", audio_codec, "-flush_packets", "1" ])

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
                await kill_process(process)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return audio_format, _iterator()

    def _build_video_input_args(
        self,
        system: str,
        display: int,
        framerate: float,
        region: Optional[Dict[str, int]] = None,
    ) -> List[str]:
        if system == "Darwin":
            # avfoundation video inputs are indexed independently of audio;
            # the "<display>:none" form selects a display without an audio device.
            # avfoundation can't crop at input; the region is applied via a
            # -vf crop filter downstream (see _start_video_capture).
            return [
                "-f", "avfoundation",
                "-framerate", str(framerate),
                "-capture_cursor", "1",
                "-i", f"{display}:none",
            ]

        if system == "Windows":
            argv: List[str] = [
                "-f", "gdigrab",
                "-framerate", str(framerate),
            ]

            if region is not None:
                # gdigrab reads a rectangle when offsets + video_size are set.
                argv.extend([
                    "-offset_x", str(region["x"]),
                    "-offset_y", str(region["y"]),
                    "-video_size", f"{region['width']}x{region['height']}",
                ])

            argv.extend([ "-i", "desktop" ])

            return argv

        if system == "Linux":
            display_env = os.environ.get("DISPLAY", ":0.0")
            argv: List[str] = [
                "-f", "x11grab",
                "-framerate", str(framerate),
            ]

            if region is not None:
                # x11grab accepts the region size at the input and the origin
                # baked into the display spec (e.g. ':0.0+100,200').
                argv.extend([ "-video_size", f"{region['width']}x{region['height']}" ])
                argv.extend([ "-i", f"{display_env}+{region['x']},{region['y']}" ])
            else:
                argv.extend([ "-i", display_env ])

            return argv

        raise NotImplementedError(f"Video capture is not supported on platform: {system}")

    def _build_audio_input_args(self, system: str, audio_source: ScreenCaptureAudioSource) -> List[str]:
        if system == "Darwin":
            # macOS system loopback is not reachable via avfoundation; that path
            # is handled by _start_macos_system_audio. Only microphone lands here.
            if audio_source == ScreenCaptureAudioSource.MICROPHONE:
                return [ "-f", "avfoundation", "-i", ":default" ]

        if system == "Windows":
            if audio_source == ScreenCaptureAudioSource.SYSTEM:
                # WASAPI loopback of the default render endpoint.
                return [ "-f", "dshow", "-i", "audio=virtual-audio-capturer" ]

            if audio_source == ScreenCaptureAudioSource.MICROPHONE:
                return [ "-f", "dshow", "-i", "audio=default" ]

        if system == "Linux":
            if audio_source == ScreenCaptureAudioSource.SYSTEM:
                # PulseAudio auto-creates a monitor source for the default sink.
                return [ "-f", "pulse", "-i", "default.monitor" ]

            if audio_source == ScreenCaptureAudioSource.MICROPHONE:
                return [ "-f", "pulse", "-i", "default" ]

        raise NotImplementedError(f"Audio source '{audio_source.value}' is not supported on platform: {system}")

    async def _start_macos_system_audio(
        self,
        audio_format: str,
        audio_codec: str,
        audio_bitrate: Optional[int],
        duration: Optional[float],
    ) -> AsyncIterator[bytes]:
        """Pipe audiotee PCM into ffmpeg to encode macOS system loopback."""
        audiotee_path = shutil.which("audiotee")

        if not audiotee_path:
            raise RuntimeError(
                "macOS system audio capture requires the 'audiotee' CLI on PATH "
                "(see https://github.com/makeusabrew/audiotee). Install it with 'brew install audiotee' "
                "or set audio_source: microphone to fall back to the microphone."
            )

        # audiotee's actual output is 32-bit float little-endian, mono, at the
        # tap device's native sample rate (48 kHz on typical Macs). Verified
        # against audiotee's stderr metadata event; pass matching flags to
        # ffmpeg so it doesn't have to guess.
        sample_rate = 48000
        channels = 1

        audiotee_command = [ audiotee_path, "--chunk-duration", "0.1" ]
        ffmpeg_command: List[str] = [
            "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning",
            "-f", "f32le",
            "-ar", str(sample_rate),
            "-ac", str(channels),
            "-i", "pipe:0",
            "-c:a", audio_codec,
        ]

        if audio_bitrate:
            ffmpeg_command.extend([ "-b:a", str(audio_bitrate) ])

        if duration is not None:
            ffmpeg_command.extend([ "-t", str(duration) ])

        ffmpeg_command.extend([ "-f", self._audio_muxer(audio_format), "pipe:1" ])

        logging.debug("Starting audiotee | ffmpeg pipeline for macOS system audio")

        # asyncio's subprocess.PIPE hands back a StreamReader, which has no
        # fileno() and cannot be fed as another process's stdin. Build an
        # os-level pipe ourselves so audiotee → ffmpeg is a real kernel pipe.
        pipe_read_fd, pipe_write_fd = os.pipe()

        try:
            audiotee_proc = await asyncio.create_subprocess_exec(
                *audiotee_command,
                stdout=pipe_write_fd,
                stderr=asyncio.subprocess.DEVNULL,
            )
            ffmpeg_proc = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=pipe_read_fd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        finally:
            # Both processes own their end now; close ours so EOF propagates
            # when either side exits.
            os.close(pipe_read_fd)
            os.close(pipe_write_fd)

        queue: asyncio.Queue = asyncio.Queue(maxsize=_CHUNK_QUEUE_SIZE)

        async def _reader() -> None:
            try:
                while True:
                    chunk = await ffmpeg_proc.stdout.read(65536)
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
                await kill_process(ffmpeg_proc)
                await kill_process(audiotee_proc)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return _iterator()

    @staticmethod
    def _resolve_container_format(encoding: Optional[VideoAudioEncodingParams]) -> str:
        if encoding and encoding.format:
            return encoding.format.lower()

        return _DEFAULT_VIDEO_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: Optional[VideoAudioEncodingParams]) -> str:
        if encoding and encoding.video and encoding.video.codec:
            return encoding.video.codec

        return _DEFAULT_VIDEO_CODEC

    @staticmethod
    def _resolve_audio_format(encoding: Optional[VideoAudioEncodingParams]) -> str:
        if encoding and encoding.format:
            format = encoding.format.lower()

            # Audio-only containers pass through untouched.
            if format in ("aac", "wav", "flac", "mp3", "ogg", "opus", "m4a"):
                return format

            # Video-oriented containers get mapped to a matching audio-only
            # container so decoders can consume the audio stream in isolation.
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
    def _container_muxer(video_format: str) -> str:
        # ffmpeg muxer names mostly match extensions; the exception is "ts",
        # which is the standard content-type shorthand but registers in ffmpeg
        # as "mpegts". mp4 stays "mp4" (paired with fragmented movflags above).
        if video_format == "ts":
            return "mpegts"

        return video_format

    @staticmethod
    def _audio_muxer(audio_format: str) -> str:
        if audio_format == "m4a":
            return "ipod"  # fragmented-mp4 audio-only muxer usable for pipe output

        if audio_format == "aac":
            return "adts"

        return audio_format

@register_screen_capture_service(ScreenCaptureDriver.FFMPEG)
class FFmpegScreenCaptureService(ScreenCaptureService):
    def __init__(self, id: str, config: ScreenCaptureComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: ScreenCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegScreenCaptureAction(action).run(context)
