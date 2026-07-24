from __future__ import annotations

from typing import Optional, Set, Tuple, List, Dict, Callable, Any
from collections.abc import AsyncIterator, AsyncIterable
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriver
from mindor.dsl.schema.action import VideoEncoderActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.channels.subprocess_stream import SubprocessStreamChannel
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from PIL import Image as PILImage
from ..base import VideoEncoderService, register_video_encoder_service
from ..base import ComponentActionContext
from .common import VideoEncoderAction
import asyncio, io, os

# Input container formats safe to feed through ffmpeg pipe:0. Other formats
# (mp4/mov/mkv/webm/avi/...) or unknown formats are spooled to a temp file
# first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "flv", "mpegts", "ts", "mp3", "wav", "flac", "ogg", "opus", "aac",
}

# Output container formats that can be written to ffmpeg's stdout (no post-write seek).
# Others (mp4/mov/mkv/avi/...) need a real file path with seeking — typically for moov atom
# placement, index tables, +faststart, etc.
_STREAMABLE_OUTPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

# `pass_fds` and inherited pipe descriptors are POSIX-only; Windows can't
# hand a `pipe:<fd>` beyond stdin to a child. When False, callers must spool
# the second live stream to a temp file so ffmpeg reads it as a file input.
_SUPPORTS_FD_INPUT: bool = os.name == "posix"

class FFmpegVideoEncoderAction(VideoEncoderAction):
    async def _encode_from_video(
        self,
        video: MediaSource,
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = params["format"]

        if streaming and format.lower() not in _STREAMABLE_OUTPUT_FORMATS:
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        video_path, video_spooled = await self._resolve_input_path(video)
        audio_path, audio_spooled = (await self._resolve_input_path(audio)) if audio is not None else (None, False)

        # On Windows only `pipe:0` is available. If both sides would end up as
        # live streams, force-spool the audio side so the video keeps its pipe path.
        if not _SUPPORTS_FD_INPUT and audio is not None:
            if video_path is None and audio_path is None:
                audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
                audio_spooled = True

        # The first live stream takes stdin (`pipe:0`); any further one rides an
        # inherited descriptor (POSIX-only). File paths are resolved to themselves.
        stdin_owner: Optional[MediaSource] = None
        fd_channels: List[SubprocessStreamChannel] = []

        video_input, stdin_owner = self._resolve_input_source(video, video_path, stdin_owner, fd_channels)
        audio_input, stdin_owner = (
            self._resolve_input_source(audio, audio_path, stdin_owner, fd_channels)
            if audio is not None else (None, stdin_owner)
        )

        command = [ "ffmpeg", "-hide_banner", "-y" ]

        if video.attrs.get("resolution"):
            command.extend([ "-s", str(video.attrs["resolution"]) ])

        if video.attrs.get("fps"):
            command.extend([ "-r", str(video.attrs["fps"]) ])

        command.extend([ "-i", video_input ])

        if audio_input is not None:
            command.extend([ "-i", audio_input ])
            command.extend([ "-map", "0:v", "-map", "1:a" ])

        for option, value in self._resolve_encoding_options(params, has_audio=audio_input is not None).items():
            command.extend([ option, value ])

        if audio_input is not None:
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

        source = stdin_owner.stream if stdin_owner is not None else None

        logging.debug("Encoding video to '%s'", format)

        if streaming:
            return await self._encode_to_stream(command, source, fd_channels, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, source, fd_channels, format, _cleanup, cancellation_token)

    async def _encode_from_frames(
        self,
        frames: List[PILImage.Image],
        audio: Optional[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format, frame_rate = params["format"], params["frame_rate"] or 30

        if streaming and format.lower() not in _STREAMABLE_OUTPUT_FORMATS:
            logging.warning("Format '%s' is not streamable; falling back to file output.", format)
            streaming = False

        audio_path, audio_spooled = (await self._resolve_input_path(audio)) if audio is not None else (None, False)

        # `image2pipe` already claims stdin. If audio remains a live stream, it
        # needs an inherited descriptor — POSIX-only. Force-spool on Windows.
        if not _SUPPORTS_FD_INPUT and audio is not None and audio_path is None:
            audio_path = await save_stream_to_temporary_file(audio.stream, audio.format)
            audio_spooled = True

        fd_channels: List[SubprocessStreamChannel] = []
        audio_input: Optional[str] = None

        if audio is not None:
            if audio_path is not None:
                audio_input = audio_path
            else:
                channel = SubprocessStreamChannel(audio.stream)
                fd_channels.append(channel)
                audio_input = f"pipe:{channel.read_fd}"

        command = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-f", "image2pipe", "-framerate", str(frame_rate), "-i", "pipe:0" ])

        if audio_input is not None:
            command.extend([ "-i", audio_input ])
            command.extend([ "-map", "0:v", "-map", "1:a" ])

        for option, value in self._resolve_encoding_options(params, has_audio=audio_input is not None).items():
            command.extend([ option, value ])

        if audio_input is not None:
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

        logging.debug("Encoding %d frames to '%s'", len(frames), format)

        if streaming:
            return await self._encode_to_stream(command, _frames_bytes(), fd_channels, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, _frames_bytes(), fd_channels, format, _cleanup, cancellation_token)

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

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before encoding")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    @staticmethod
    def _resolve_input_source(
        media: MediaSource,
        media_path: Optional[str],
        stdin_owner: Optional[MediaSource],
        fd_channels: List[SubprocessStreamChannel],
    ) -> Tuple[str, Optional[MediaSource]]:
        """Assign one input to a file path, `pipe:0`, or an inherited descriptor.

        `media_path` is the result of `_resolve_input_path` — a real path if the
        source was spooled or already on disk, or None if it should be fed as a
        live stream. Live streams take stdin (`pipe:0`) first; any further one
        rides an inherited fd, which is POSIX-only.
        """
        if media_path is not None:
            return media_path, stdin_owner

        if stdin_owner is None:
            return "pipe:0", media

        if not _SUPPORTS_FD_INPUT:
            raise RuntimeError(
                "Multiple live streams are not supported on this platform; "
                "spool one input to a file before encoding."
            )

        channel = SubprocessStreamChannel(media.stream)
        fd_channels.append(channel)

        return f"pipe:{channel.read_fd}", stdin_owner

    def _resolve_encoding_options(self, params: Dict[str, Any], has_audio: bool) -> Dict[str, str]:
        options: Dict[str, str] = {}

        if params["video_codec"]:
            options["-c:v"] = params["video_codec"]

        if params["video_bitrate"]:
            options["-b:v"] = params["video_bitrate"]

        if params["resolution"]:
            options["-s"] = params["resolution"]

        if params["fps"]:
            options["-r"] = str(params["fps"])

        # yuv420p ensures broad player compatibility for image-derived streams.
        if params["video_codec"] in ("libx264", "libx265"):
            options["-pix_fmt"] = "yuv420p"

        if has_audio:
            if params["audio_codec"]:
                options["-c:a"] = params["audio_codec"]

            if params["audio_bitrate"]:
                options["-b:a"] = params["audio_bitrate"]

        return options

    async def _encode_to_file(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        fd_channels: List[SubprocessStreamChannel],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = create_temporary_file(format)

        command = command + [ "-movflags", "+faststart", output_path ]

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
                raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video encoding cancelled")
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

            cleanup()

        logging.debug("Video encoding completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _encode_to_stream(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
        fd_channels: List[SubprocessStreamChannel],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg writing to stdout and wrap the byte stream as a VideoStreamResource."""
        command = command + [ "-f", format, "pipe:1" ]
        error: list = []

        async def _handle_stdout(reader: asyncio.StreamReader) -> AsyncIterator[bytes]:
            while True:
                chunk = await reader.read(65536)

                if not chunk:
                    break

                yield chunk

        async def _handle_stderr(reader: asyncio.StreamReader) -> None:
            while True:
                line = await reader.readline()

                if not line:
                    break

                error.append(line)

        async def _on_started() -> None:
            # ffmpeg owns the read ends now; each start() drops the parent's
            # copy so ffmpeg can see EOF, then begins pumping the source.
            for channel in fd_channels:
                await channel.start()

        async def _stream() -> AsyncIterator[bytes]:
            watcher_task: Optional[asyncio.Task] = None
            try:
                async with stream_subprocess(
                    command,
                    source=source,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
                    pass_fds=tuple(channel.read_fd for channel in fd_channels),
                    on_started=_on_started,
                ) as (process, chunks, _):
                    if cancellation_token is not None:
                        async def _watch_cancellation() -> None:
                            while not cancellation_token.is_cancelled():
                                if process.returncode is not None:
                                    return
                                await asyncio.sleep(0.2)
                            process.kill()

                        watcher_task = asyncio.create_task(_watch_cancellation())

                    async for chunk in chunks:
                        yield chunk

                if process.returncode is not None and process.returncode != 0:
                    error_message = b"".join(error).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                for channel in fd_channels:
                    await channel.close()

                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

@register_video_encoder_service(VideoEncoderDriver.FFMPEG)
class FFmpegVideoEncoderService(VideoEncoderService):
    def __init__(self, id: str, config: VideoEncoderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoEncoderActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoEncoderAction(action).run(context, loop)
