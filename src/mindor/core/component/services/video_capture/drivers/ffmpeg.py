from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoCaptureComponentConfig
from mindor.dsl.schema.action import VideoCaptureActionConfig, VideoCaptureSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.utils.shell import kill_process
from mindor.core.logger import logging
from ..base import VideoCaptureService, VideoCaptureDriver, register_video_capture_service
from ..base import ComponentActionContext
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from .common import VideoCaptureAction
import asyncio, platform, time

_STREAM_END = object()
_CHUNK_QUEUE_SIZE = 32

# MPEG-TS is the default for the same reason as screen-capture: each packet is
# self-contained so encoded chunks are available immediately over a pipe.
_DEFAULT_VIDEO_FORMAT = "ts"

# libx264 with `-preset veryfast -tune zerolatency` cannot keep up with 1080p30
# camera input on typical laptop CPUs, so it silently drops frames — producing
# the "choppy 9 fps" video the smoke test caught. macOS ships h264_videotoolbox
# which offloads to the hardware encoder and easily hits real-time at 1080p60.
# Linux and Windows have no equally universal hardware encoder, so they stay
# on libx264 and users needing higher resolutions should override `encoding.video.codec`.
_DEFAULT_VIDEO_CODEC_BY_SYSTEM = {
    "Darwin":  "h264_videotoolbox",
    "Windows": "libx264",
    "Linux":   "libx264",
}
_FALLBACK_VIDEO_CODEC = "libx264"

# Default device index per platform when the user leaves `device` unset.
# On Linux we default to /dev/video0 which is where v4l2 usually exposes the
# first camera.
_DEFAULT_DEVICE = {
    "Darwin":  "0",
    "Windows": None,  # dshow has no numeric default; user must set device= or list devices.
    "Linux":   "/dev/video0",
}

class FFmpegVideoCaptureAction(VideoCaptureAction):
    async def _capture(self, params: Dict[str, Any]) -> Dict[str, Any]:
        system = platform.system()
        capture_pts = time.monotonic()

        video_format, video_iterator = await self._start_video_capture(system, params)
        video_stream = VideoStreamResource(
            AsyncIterableStreamResource(video_iterator),
            format=video_format,
            attrs={ "capture_pts": capture_pts },
        )

        return {
            "video":       video_stream,
            "capture_pts": capture_pts,
        }

    async def _start_video_capture(
        self,
        system: str,
        params: Dict[str, Any],
    ) -> Tuple[str, AsyncIterator[bytes]]:
        source       = params["source"]
        encoding     = params["encoding"]
        framerate    = params["framerate"]
        device       = params["device"]
        resolution   = params.get("resolution")
        pixel_format = params.get("pixel_format")

        if source != VideoCaptureSource.CAMERA:
            raise NotImplementedError(f"video-capture source '{source.value}' is not supported yet")

        video_format  = self._resolve_container_format(encoding)
        video_codec   = self._resolve_video_codec(encoding, system)
        video_bitrate = encoding.video.bitrate if encoding and encoding.video and encoding.video.bitrate else None

        command: List[str] = [ "ffmpeg", "-hide_banner", "-nostats", "-loglevel", "warning" ]
        command.extend(self._build_video_input_args(system, device, framerate, resolution, pixel_format))
        command.extend([ "-c:v", video_codec ])

        # `-preset` and `-tune` are x264/x265-only flags; hardware encoders
        # like h264_videotoolbox reject them. Real-time keyframe cadence is
        # still important on any codec, so `-g` and `-pix_fmt` stay universal.
        if video_codec in ("libx264", "libx265"):
            command.extend([ "-preset", "veryfast", "-tune", "zerolatency" ])

        command.extend([
            "-g", str(max(1, int(framerate))),
            "-pix_fmt", "yuv420p",
            "-flush_packets", "1",
        ])

        # Tag the encoded stream with a well-defined colorspace. Camera
        # inputs (avfoundation uyvy422, dshow, v4l2) leave color metadata
        # unset, so players fall back to guessing — which is what causes
        # washed-out or oversaturated playback. bt709 tv-range matches how
        # consumer webcams and capture cards actually deliver pixels.
        command.extend([
            "-color_range",     "tv",
            "-colorspace",      "bt709",
            "-color_primaries", "bt709",
            "-color_trc",       "bt709",
        ])

        # x264 also writes the same tags into the H.264 VUI so decoders
        # that ignore container-level metadata still see them.
        if video_codec == "libx264":
            command.extend([ "-x264opts", "colorprim=bt709:transfer=bt709:colormatrix=bt709" ])

        if video_bitrate:
            command.extend([ "-b:v", str(video_bitrate) ])

        if params["duration"] is not None:
            command.extend([ "-t", str(params["duration"]) ])

        command.extend([ "-f", self._container_muxer(video_format) ])

        if video_format in ("mp4", "mov", "m4v"):
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
                await kill_process(process, timeout=2.0)
                reader_task.cancel()
                try:
                    await reader_task
                except (asyncio.CancelledError, Exception):
                    pass

        return video_format, _iterator()

    def _build_video_input_args(
        self,
        system: str,
        device: Optional[Any],
        framerate: float,
        resolution: Optional[Dict[str, int]],
        pixel_format: Optional[str],
    ) -> List[str]:
        resolved_device = self._resolve_device(system, device)

        if system == "Darwin":
            # avfoundation video-only input: "<video>:none". Device can be a
            # numeric index (as string) or a device name.
            args: List[str] = [
                "-f", "avfoundation",
                "-framerate", str(framerate),
            ]

            if resolution is not None:
                args.extend([ "-video_size", f"{resolution['width']}x{resolution['height']}" ])

            # avfoundation cameras negotiate a device-native pixel format
            # (typically uyvy422); ffmpeg's default request of yuv420p fails
            # with "Selected pixel format is not supported". Default to
            # uyvy422 so a plain `source: camera` config works out of the
            # box; users can still override.
            args.extend([ "-pixel_format", pixel_format or "uyvy422" ])
            
            args.extend([ "-i", f"{resolved_device}:none" ])

            return args

        if system == "Windows":
            args: List[str] = [
                "-f", "dshow",
                "-framerate", str(framerate),
            ]

            if resolution is not None:
                args.extend([ "-video_size", f"{resolution['width']}x{resolution['height']}" ])

            if pixel_format is not None:
                args.extend([ "-pixel_format", pixel_format ])

            args.extend([ "-i", f"video={resolved_device}" ])

            return args

        if system == "Linux":
            args: List[str] = [
                "-f", "v4l2",
                "-framerate", str(framerate),
            ]

            if resolution is not None:
                args.extend([ "-video_size", f"{resolution['width']}x{resolution['height']}" ])

            if pixel_format is not None:
                args.extend([ "-input_format", pixel_format ])

            args.extend([ "-i", str(resolved_device) ])

            return args

        raise NotImplementedError(f"Video capture is not supported on platform: {system}")

    @staticmethod
    def _resolve_device(system: str, device: Optional[Any]) -> str:
        if device is not None:
            return str(device)

        default = _DEFAULT_DEVICE.get(system)

        if default is None:
            raise ValueError(
                f"video-capture 'device' is required on {system}; specify a camera device name or index."
            )

        return default

    @staticmethod
    def _resolve_container_format(encoding: Optional[VideoAudioEncodingParams]) -> str:
        if encoding and encoding.format:
            return encoding.format.lower()

        return _DEFAULT_VIDEO_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: Optional[VideoAudioEncodingParams], system: str) -> str:
        if encoding and encoding.video and encoding.video.codec:
            return encoding.video.codec

        return _DEFAULT_VIDEO_CODEC_BY_SYSTEM.get(system, _FALLBACK_VIDEO_CODEC)

    @staticmethod
    def _container_muxer(video_format: str) -> str:
        if video_format == "ts":
            return "mpegts"

        return video_format

@register_video_capture_service(VideoCaptureDriver.FFMPEG)
class FFmpegVideoCaptureService(VideoCaptureService):
    def __init__(self, id: str, config: VideoCaptureComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def _run(self, action: VideoCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoCaptureAction(action).run(context)
