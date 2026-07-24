from __future__ import annotations

from typing import Optional, Union, List, Dict, Set, Tuple, Any
from collections.abc import AsyncIterable
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriver
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ..base import RtmpPublisherService, register_rtmp_publisher_service
from ..base import ComponentActionContext
from .common import RtmpPublisherAction
import asyncio, os

# Container formats safe to feed through ffmpeg pipe:0. Other formats
# (mp4/mov/mkv/webm/avi/...) or unknown formats are spooled to a temp file
# first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "flv", "mpegts", "ts", "mp3", "wav", "flac", "ogg", "opus", "aac",
}

# `pass_fds` and inherited pipe descriptors are POSIX-only; Windows can't
# hand a `pipe:<fd>` beyond stdin to a child. When False, callers must spool
# the second live stream to a temp file so ffmpeg reads it as a file input.
_SUPPORTS_FD_INPUT: bool = os.name == "posix"

class FFmpegRtmpPublisher:
    """One RTMP publish: spawn ffmpeg, push to the URL, exit.

    Each `publish()` call spawns a fresh ffmpeg process, opens a new RTMP
    connection, streams the input, and terminates. We don't hold a
    persistent process across items because there's no reliable way to
    notice the peer (e.g. YouTube) closing the session — TCP writes keep
    succeeding into a dead socket until keepalive eventually fires.
    """
    def __init__(self, url: str, params: Dict[str, Any]):
        self.url: str = url
        self.params: Dict[str, Any] = params

    async def publish(
        self,
        video: Optional[Union[MediaSource, str]],
        video_attrs: Optional[Dict[str, Any]],
        audio: Optional[Union[MediaSource, str]],
        audio_attrs: Optional[Dict[str, Any]],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        has_video = video is not None
        has_audio = audio is not None

        # The first MediaSource takes stdin (`pipe:0`); any further one
        # rides an inherited descriptor.
        stdin_owner: Optional[MediaSource] = None
        fd_channels: List[SubprocessStreamChannel] = []

        video_input: Optional[str] = None
        audio_input: Optional[str] = None

        if has_video:
            video_input, stdin_owner = self._resolve_input_source(video, stdin_owner, fd_channels)

        if has_audio:
            audio_input, stdin_owner = self._resolve_input_source(audio, stdin_owner, fd_channels)

        command = self._build_publish_command(video_input, video_attrs, audio_input, audio_attrs)

        logging.debug("Publishing to RTMP: %s", self.url)

        source: Optional[AsyncIterable[bytes]] = stdin_owner.stream if stdin_owner is not None else None

        async def _on_started() -> None:
            # ffmpeg owns the read ends now; each start() drops the parent's
            # copy so ffmpeg can see EOF, then begins pumping the source.
            for channel in fd_channels:
                await channel.start()

        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            source,
            stderr_handler=lambda r: r.read(),
            pass_fds=tuple(channel.read_fd for channel in fd_channels),
            on_started=_on_started,
        ))

        watcher_task: Optional[asyncio.Task] = None

        if cancellation_token is not None:
            async def _watch_cancellation() -> None:
                while not cancellation_token.is_cancelled():
                    if process_task.done():
                        return
                    await asyncio.sleep(0.2)
                process_task.cancel()

            watcher_task = asyncio.create_task(_watch_cancellation())

        try:
            process, _, error = await process_task

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg RTMP publish failed (exit code {process.returncode}): {error_message}")

            logging.debug("RTMP publish completed: %s", self.url)
        except asyncio.CancelledError:
            logging.info("RTMP publish cancelled for %s", self.url)
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            for channel in fd_channels:
                await channel.close()

    @staticmethod
    def _resolve_input_source(
        source: Union[MediaSource, str],
        stdin_owner: Optional[MediaSource],
        fd_channels: List[SubprocessStreamChannel],
    ) -> Tuple[str, Optional[MediaSource]]:
        """Assign one input to `pipe:0` or an inherited descriptor.

        The first MediaSource is claimed for stdin (`pipe:0`); any further
        one is fed over its own inherited fd, which is POSIX-only. Returns
        the resolved ffmpeg input spec plus the updated `stdin_owner`
        (unchanged when `source` was a file path).
        """
        if isinstance(source, str):
            return source, stdin_owner

        if stdin_owner is None:
            return "pipe:0", source

        if not _SUPPORTS_FD_INPUT:
            raise RuntimeError(
                "Multiple live streams are not supported on this platform; "
                "spool one input to a file before publishing."
            )

        channel = SubprocessStreamChannel(source.stream)
        fd_channels.append(channel)

        return f"pipe:{channel.read_fd}", stdin_owner

    def _build_publish_command(
        self,
        video_input: Optional[str],
        video_attrs: Optional[Dict[str, Any]],
        audio_input: Optional[str],
        audio_attrs: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Build the ffmpeg command that publishes to RTMP.

        `video_input` / `audio_input` are already-resolved ffmpeg input specs:
        a file path, `pipe:0`, or `pipe:<fd>` for an inherited descriptor.
        """
        has_video = video_input is not None
        has_audio = audio_input is not None

        command = [ "ffmpeg", "-hide_banner", "-y" ]

        if has_video:
            if video_attrs and video_attrs.get("resolution"):
                command.extend([ "-s", str(video_attrs["resolution"]) ])
            if video_attrs and video_attrs.get("fps"):
                command.extend([ "-r", str(video_attrs["fps"]) ])
            command.extend([ "-i", video_input ])

        if has_audio:
            if audio_attrs and audio_attrs.get("sample_rate"):
                command.extend([ "-ar", str(audio_attrs["sample_rate"]) ])
            if audio_attrs and audio_attrs.get("channels"):
                command.extend([ "-ac", str(audio_attrs["channels"]) ])
            command.extend([ "-i", audio_input ])
            if has_video:
                command.extend([ "-map", "0:v", "-map", "1:a", "-shortest" ])

        for option, value in self._resolve_encoding_options(has_video=has_video, has_audio=has_audio).items():
            command.extend([ option, value ])

        command.extend([ "-f", self.params["format"], self.url ])

        return command

    def _resolve_encoding_options(self, has_video: bool, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        if has_video:
            if self.params["video_codec"]:
                options["-c:v"] = self.params["video_codec"]

            if self.params["video_bitrate"]:
                options["-b:v"] = self.params["video_bitrate"]

            if self.params["resolution"]:
                options["-s"] = self.params["resolution"]

            if self.params["fps"]:
                options["-r"] = str(self.params["fps"])

            if self.params["video_codec"] in ("libx264", "libx265"):
                options["-pix_fmt"] = "yuv420p"

        if has_audio:
            if self.params["audio_codec"]:
                options["-c:a"] = self.params["audio_codec"]

            if self.params["audio_bitrate"]:
                options["-b:a"] = self.params["audio_bitrate"]

        return options

class FFmpegRtmpPublisherAction(RtmpPublisherAction):
    async def _publish(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_path, video_spooled = (await self._resolve_input_path(video)) if video is not None else (None, False)
        audio_path, audio_spooled = (await self._resolve_input_path(audio)) if audio is not None else (None, False)

        # POSIX can hand a second live stream to ffmpeg over an inherited
        # descriptor, so both sides may stay as streams. On Windows only
        # `pipe:0` is available — spool the audio side so the video keeps
        # its pipe path.
        if not _SUPPORTS_FD_INPUT and video is not None and audio is not None:
            if video_path is None and audio_path is None:
                audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
                audio_spooled = True

        try:
            publisher = FFmpegRtmpPublisher(url, params)
            await publisher.publish(
                video_path if video_path is not None else video,
                video.attrs if video is not None else None,
                audio_path if audio_path is not None else audio,
                audio.attrs if audio is not None else None,
                cancellation_token,
            )
        finally:
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

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (flv, mpegts, mp3, wav, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format and source.format.lower() in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before publishing")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

@register_rtmp_publisher_service(RtmpPublisherDriver.FFMPEG)
class FFmpegRtmpPublisherService(RtmpPublisherService):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegRtmpPublisherAction(action).run(context, loop)
