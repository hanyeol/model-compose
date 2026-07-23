from __future__ import annotations

from typing import Optional, List, Dict, Tuple, Callable, Any
from collections.abc import AsyncIterator, AsyncIterable
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriver
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from PIL import Image as PILImage
from ..base import RtmpPublisherService, register_rtmp_publisher_service
from ..base import ComponentActionContext
from .common import RtmpPublisherAction
import asyncio, io, os


class FFmpegRtmpPublisherAction(RtmpPublisherAction):
    async def _publish_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_path, video_spooled = await self._resolve_input_path(video)
        audio_path, audio_spooled = (None, False)

        if audio is not None:
            audio_path, audio_spooled = await self._resolve_input_path(audio)

        command = [ "ffmpeg", "-hide_banner", "-y" ]

        if video.attrs.get("resolution"):
            command.extend([ "-s", str(video.attrs["resolution"]) ])

        if video.attrs.get("fps"):
            command.extend([ "-r", str(video.attrs["fps"]) ])

        command.extend([ "-i", video_path if video_path is not None else "pipe:0" ])

        if audio_path is not None:
            command.extend([ "-i", audio_path ])
            command.extend([ "-map", "0:v", "-map", "1:a" ])

        for option, value in self._resolve_encoding_options(params, has_video=True, has_audio=audio_path is not None).items():
            command.extend([ option, value ])

        if audio_path is not None:
            command.append("-shortest")

        def _cleanup() -> None:
            if video_spooled and video_path is not None:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass
            if audio_spooled and audio_path is not None:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        source_bytes = video.stream if video_path is None else None

        logging.debug(f"Publishing video to RTMP: {url}")

        await self._publish(url, command, source_bytes, params, _cleanup, cancellation_token)

    async def _publish_from_frames(
        self,
        frames: List[PILImage.Image],
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        frame_rate = params["frame_rate"] or 30
        audio_path, audio_spooled = (None, False)

        if audio is not None:
            audio_path, audio_spooled = await self._resolve_input_path(audio)

        command = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-f", "image2pipe", "-framerate", str(frame_rate), "-i", "pipe:0" ])

        if audio_path is not None:
            command.extend([ "-i", audio_path ])
            command.extend([ "-map", "0:v", "-map", "1:a" ])

        for option, value in self._resolve_encoding_options(params, has_video=True, has_audio=audio_path is not None).items():
            command.extend([ option, value ])

        if audio_path is not None:
            command.append("-shortest")

        def _cleanup() -> None:
            if audio_spooled and audio_path is not None:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        async def _frames_bytes() -> AsyncIterator[bytes]:
            for frame in frames:
                buffer = io.BytesIO()
                await asyncio.to_thread(frame.save, buffer, "PNG")
                yield buffer.getvalue()

        logging.debug(f"Publishing {len(frames)} frames to RTMP: {url}")

        await self._publish(url, command, _frames_bytes(), params, _cleanup, cancellation_token)

    async def _publish_audio_only(
        self,
        audio: MediaSource,
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        audio_path, audio_spooled = await self._resolve_input_path(audio)

        command = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-i", audio_path if audio_path is not None else "pipe:0" ])

        for option, value in self._resolve_encoding_options(params, has_video=False, has_audio=True).items():
            command.extend([ option, value ])

        def _cleanup() -> None:
            if audio_spooled and audio_path is not None:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

        source_bytes = audio.stream if audio_path is None else None

        logging.debug(f"Publishing audio-only to RTMP: {url}")

        await self._publish(url, command, source_bytes, params, _cleanup, cancellation_token)

    def _resolve_encoding_options(self, params: Dict[str, Any], has_video: bool, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        if has_video:
            if params["video_codec"]:
                options["-c:v"] = params["video_codec"]

            if params["video_bitrate"]:
                options["-b:v"] = params["video_bitrate"]

            if params["resolution"]:
                options["-s"] = params["resolution"]

            if params["fps"]:
                options["-r"] = str(params["fps"])

            # yuv420p ensures broad player compatibility (Flash Player, browser HTML5 video, etc.).
            if params["video_codec"] in ("libx264", "libx265"):
                options["-pix_fmt"] = "yuv420p"

        if has_audio:
            if params["audio_codec"]:
                options["-c:a"] = params["audio_codec"]

            if params["audio_bitrate"]:
                options["-b:a"] = params["audio_bitrate"]

        return options

    async def _publish(
        self,
        url: str,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        params: Dict[str, Any],
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        """Run ffmpeg to the RTMP endpoint. Blocks until the publish stream ends."""
        command = command + [ "-f", params["format"], url ]

        try:
            process, _, error = await run_subprocess(
                command,
                source,
                stderr_handler=lambda r: r.read(),
            )

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg RTMP publish failed (exit code {process.returncode}): {error_message}")
        finally:
            cleanup()

        logging.debug(f"RTMP publish completed: {url}")

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """Return a filesystem path for `source`, spooling to a temp file if needed.

        Returns (path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True


@register_rtmp_publisher_service(RtmpPublisherDriver.FFMPEG)
class FFmpegRtmpPublisherService(RtmpPublisherService):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegRtmpPublisherAction(action).run(context, loop)
