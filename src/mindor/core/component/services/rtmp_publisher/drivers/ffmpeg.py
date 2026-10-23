from __future__ import annotations

from typing import Optional, Union, Deque, List, Dict, Tuple, Any
from collections import deque
from collections.abc import AsyncIterable
from urllib.parse import urlsplit, urlunsplit
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriverType
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from mindor.core.utils.audio import is_pcm_format
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel
from mindor.core.utils.shell import run_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import RtmpPublisherDriver, register_rtmp_publisher_driver
from ..base import ComponentActionContext
from .common import RtmpPublisherAction
import asyncio, os

# RTMP is virtually always flv-wrapped h264/aac.
_DEFAULT_FORMAT: str = "flv"
_DEFAULT_VIDEO_CODEC: str = "libx264"
_DEFAULT_AUDIO_CODEC: str = "aac"

# `pass_fds` and inherited pipe descriptors are POSIX-only; Windows can't
# hand a `pipe:<fd>` beyond stdin to a child. When False, callers must spool
# the second live stream to a temp file so ffmpeg reads it as a file input.
_SUPPORTS_FD_INPUT: bool = os.name == "posix"

# How many ffmpeg stderr lines a failed publish reports. Only the tail is
# kept: a live publish can run for days.
_STDERR_TAIL_LINES: int = 20

_REDACTED: str = "<redacted>"

def _redact_url(url: str) -> str:
    """`url` with its secrets masked, for logs and error messages.

    RTMP ingest URLs carry the stream key as the last path segment
    (rtmp://a.rtmp.youtube.com/live2/<key>); some add tokens in the query
    (Facebook) or credentials before the host. Whoever holds the key can
    broadcast to the channel, so none of these may reach a log. A plain file
    path used as the endpoint comes back unchanged.
    """
    parts = urlsplit(url)

    if not parts.scheme or not parts.netloc:
        return url

    netloc = parts.netloc

    if parts.password is not None:
        userinfo, _, host = netloc.rpartition("@")
        netloc = f"{userinfo.partition(':')[0]}:{_REDACTED}@{host}"

    head, _, key = parts.path.rpartition("/")
    path = f"{head}/{_REDACTED}" if head and key else parts.path
    query = _REDACTED if parts.query else ""

    return urlunsplit((parts.scheme, netloc, path, query, ""))

async def _read_stderr_tail(reader: asyncio.StreamReader) -> str:
    tail: Deque[str] = deque(maxlen=_STDERR_TAIL_LINES)

    while True:
        line = await reader.readline()

        if not line:
            break

        tail.append(line.decode("utf-8", errors="replace").rstrip())

    return "\n".join(tail)

class FFmpegRtmpPublisher:
    """One RTMP publish: spawn ffmpeg, push to the URL, exit.

    Each `publish()` call spawns a fresh ffmpeg process, opens a new RTMP
    connection, streams the input, and terminates. We don't hold a
    persistent process across items because there's no reliable way to
    notice the peer (e.g. YouTube) closing the session — TCP writes keep
    succeeding into a dead socket until keepalive eventually fires.
    """
    def __init__(self, url: str, encoding: VideoAudioEncodingParams):
        self.url: str = url
        self.encoding: VideoAudioEncodingParams = encoding

    async def publish(
        self,
        video: Optional[Union[MediaSource, str]],
        video_attrs: Optional[Dict[str, Any]],
        audio: Optional[Union[MediaSource, str]],
        audio_format: Optional[str],
        audio_attrs: Optional[Dict[str, Any]],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        # The first MediaSource takes stdin (`pipe:0`); any further one
        # rides an inherited descriptor.
        stdin_owner: Optional[MediaSource] = None
        fd_channels: List[SubprocessStreamChannel] = []

        video_input, stdin_owner = self._resolve_input_source(video, stdin_owner, fd_channels) if video is not None else (None, stdin_owner)
        audio_input, stdin_owner = self._resolve_input_source(audio, stdin_owner, fd_channels) if audio is not None else (None, stdin_owner)

        command = self._build_publish_command(video_input, video_attrs, audio_input, audio_format, audio_attrs)
        source = stdin_owner.stream if stdin_owner is not None else None
        redacted_url = _redact_url(self.url)

        logging.debug("Publishing to RTMP: %s", redacted_url)

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
            stderr_handler=_read_stderr_tail,
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
                # ffmpeg names its output in its errors ("Error opening output <url>: ...").
                error_message = (error or "").replace(self.url, redacted_url)
                raise RuntimeError(f"ffmpeg RTMP publish failed (exit code {process.returncode}): {error_message}")

            logging.debug("RTMP publish completed: %s", redacted_url)
        except asyncio.CancelledError:
            logging.info("RTMP publish cancelled for %s", redacted_url)
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
        audio_format: Optional[str],
        audio_attrs: Optional[Dict[str, Any]],
    ) -> List[str]:
        """Build the ffmpeg command that publishes to RTMP.

        `video_input` / `audio_input` are already-resolved ffmpeg input specs:
        a file path, `pipe:0`, or `pipe:<fd>` for an inherited descriptor.
        """
        has_video = video_input is not None
        has_audio = audio_input is not None

        # A publish can run for days: without -nostats ffmpeg writes a progress
        # line to stderr twice a second, and only warnings and errors are worth
        # keeping for the failure message.
        command = [ resolve_ffmpeg_executable(), "-hide_banner", "-nostats", "-loglevel", "warning", "-y" ]

        if has_video:
            if video_attrs and video_attrs.get("resolution"):
                command.extend([ "-s", str(video_attrs["resolution"]) ])
            if video_attrs and video_attrs.get("frame_rate"):
                command.extend([ "-r", str(video_attrs["frame_rate"]) ])
            command.extend([ "-i", video_input ])

        if has_audio:
            if audio_format and is_pcm_format(audio_format):
                command.extend([ "-f", audio_format ])

                if audio_attrs and audio_attrs.get("sample_rate"):
                    command.extend([ "-ar", str(audio_attrs["sample_rate"]) ])
                else:
                    raise ValueError(f"Raw PCM source {audio_format!r} requires 'sample_rate' in attrs")
                if audio_attrs and audio_attrs.get("channels"):
                    command.extend([ "-ac", str(audio_attrs["channels"]) ])
                else:
                    raise ValueError(f"Raw PCM source {audio_format!r} requires 'channels' in attrs")

            command.extend([ "-i", audio_input ])

            if has_video:
                command.extend([ "-map", "0:v", "-map", "1:a", "-shortest" ])

        for option, value in self._resolve_encoding_options(has_video=has_video, has_audio=has_audio).items():
            command.extend([ option, value ])

        command.extend([ "-f", self._resolve_container_format(self.encoding), self.url ])

        return command

    def _resolve_encoding_options(self, has_video: bool, has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        video = self.encoding.video
        audio = self.encoding.audio

        if has_video:
            video_codec = self._resolve_video_codec(self.encoding)

            if video_codec:
                options["-c:v"] = video_codec

            if video and video.quality is not None:
                options["-crf"] = str(video.quality)
            elif video and video.bitrate:
                options["-b:v"] = str(video.bitrate)

            if video and video.resolution:
                options["-s"] = video.resolution

            if video and video.frame_rate is not None:
                options["-r"] = str(video.frame_rate)

            if video_codec in ("libx264", "libx265"):
                options["-pix_fmt"] = "yuv420p"

        if has_audio:
            audio_codec = self._resolve_audio_codec(self.encoding)

            if audio_codec:
                options["-c:a"] = audio_codec

            if audio and audio.bitrate:
                options["-b:a"] = str(audio.bitrate)

        return options

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams) -> str:
        if encoding.format:
            return encoding.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams) -> str:
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        return _DEFAULT_VIDEO_CODEC

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> str:
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        return _DEFAULT_AUDIO_CODEC

class FFmpegRtmpPublisherAction(RtmpPublisherAction):
    async def _publish_batch(
        self,
        videos: Optional[List[MediaSource]],
        audios: Optional[List[MediaSource]],
        url: str,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_count = len(videos) if videos is not None else (len(audios) if audios is not None else 0)

        for index in range(video_count):
            video = videos[index] if videos is not None else None
            audio = audios[index] if audios is not None else None

            if video is None and audio is None:
                continue

            await self._publish(video, audio, url, encoding, cancellation_token)

    async def _publish(
        self,
        video: Optional[MediaSource],
        audio: Optional[MediaSource],
        url: str,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> None:
        video_path, video_spooled = (await MediaInputPathResolver().resolve(video, streamable_media=[ "video" ])) if video is not None else (None, False)
        audio_path, audio_spooled = (await MediaInputPathResolver().resolve(audio, streamable_media=[ "audio", "video" ])) if audio is not None else (None, False)

        # POSIX can hand a second live stream to ffmpeg over an inherited
        # descriptor, so both sides may stay as streams. On Windows only
        # `pipe:0` is available — spool the audio side so the video keeps
        # its pipe path.
        if not _SUPPORTS_FD_INPUT and video is not None and audio is not None:
            if video_path is None and audio_path is None:
                audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
                audio_spooled = True

        try:
            publisher = FFmpegRtmpPublisher(url, encoding)
            await publisher.publish(
                video_path if video_path is not None else video,
                video.attrs if video is not None else None,
                audio_path if audio_path is not None else audio,
                audio.format if audio is not None else None,
                audio.attrs if audio is not None else None,
                cancellation_token,
            )
        finally:
            if video_spooled:
                try:
                    os.remove(video_path)
                except FileNotFoundError:
                    pass
            if audio_spooled:
                try:
                    os.remove(audio_path)
                except FileNotFoundError:
                    pass

@register_rtmp_publisher_driver(RtmpPublisherDriverType.FFMPEG)
class FFmpegRtmpPublisherService(RtmpPublisherDriver):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegRtmpPublisherAction(action).run(context)
