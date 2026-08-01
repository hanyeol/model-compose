from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

# Fallback (video_codec, audio_codec) when the encoder config leaves them unset.
_FORMAT_CODEC_MAP: Dict[str, Tuple[str, str]] = {
    "mp4":  ("libx264",    "aac"),
    "m4v":  ("libx264",    "aac"),
    "mov":  ("libx264",    "aac"),
    "mkv":  ("libx264",    "aac"),
    "webm": ("libvpx-vp9", "libopus"),
    "avi":  ("mpeg4",      "libmp3lame"),
    "ogv":  ("libtheora",  "libvorbis"),
}

# Container formats safe to feed through ffmpeg pipe:0. Other formats (mp4/mov/mkv/avi/...) or
# unknown formats are spooled to a temp file first so ffmpeg can seek for moov atoms, indexes, etc.
_STREAMABLE_INPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

# Output container formats that can be written to ffmpeg's stdout (no post-write seek).
# Others (mp4/mov/mkv/avi/...) need a real file path with seeking — typically for moov atom
# placement, index tables, +faststart, etc.
_STREAMABLE_OUTPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

class FFmpegVideoConverterAction(VideoConverterAction):
    async def _convert_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        results: List[VideoStreamResource] = []

        for video in videos:
            results.append(await self._convert(video, params["encoding"], cancellation_token))

        return results

    async def _convert(
        self,
        source: MediaSource,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = self._resolve_container_format(encoding)
        video, audio = encoding.video, encoding.audio

        input_path, spooled = await self._resolve_input_path(source)
        is_streamable_output = format.lower() in _STREAMABLE_OUTPUT_FORMATS

        command = [ "ffmpeg", "-hide_banner" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])
        if source.attrs.get("resolution"):
            command.extend([ "-s", str(source.attrs["resolution"]) ])
        if source.attrs.get("fps"):
            command.extend([ "-r", str(source.attrs["fps"]) ])
        if source.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source.attrs["pixel_format"]) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])

        video_codec = self._resolve_video_codec(encoding)
        audio_codec = self._resolve_audio_codec(encoding)

        if video_codec:
            command.extend([ "-c:v", video_codec ])
        if video and video.bitrate:
            command.extend([ "-b:v", str(video.bitrate) ])
        if audio_codec:
            command.extend([ "-c:a", audio_codec ])
        if audio and audio.bitrate:
            command.extend([ "-b:a", str(audio.bitrate) ])
        if video and video.resolution:
            command.extend([ "-s", video.resolution ])
        if video and video.fps is not None:
            command.extend([ "-r", str(video.fps) ])

        def _cleanup() -> None:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(
            "Converting video to '%s' format (%s input, %s output)",
            format,
            "path" if input_path else "pipe",
            "stream" if is_streamable_output else "file",
        )

        if is_streamable_output:
            return await self._convert_to_stream(command, source, input_path, format, _cleanup, cancellation_token)

        return await self._convert_to_file(command, source, input_path, format, _cleanup, cancellation_token)

    async def _convert_to_file(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = create_temporary_file(format)

        command = command + [ "-movflags", "+faststart", "-y", output_path ]

        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            source.stream if input_path is None else None,
            stderr_handler=lambda r: r.read(),
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
                raise RuntimeError(f"ffmpeg video conversion failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video conversion cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

        logging.debug("Video conversion completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _convert_to_stream(
        self,
        command: list,
        source: MediaSource,
        input_path: Optional[str],
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

        async def _stream() -> AsyncIterator[bytes]:
            watcher_task: Optional[asyncio.Task] = None
            try:
                async with stream_subprocess(
                    command,
                    source=source.stream if input_path is None else None,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
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
                    raise RuntimeError(f"ffmpeg video conversion failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """
        Decide how ffmpeg should read the input.

        - FileStreamResource: use its path directly (no spooling).
        - Streamable format (mpegts, webm, ...): feed via pipe:0 (returns None path).
        - Otherwise (mp4/mov/mkv/unknown/...): spool to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        if source.format in _STREAMABLE_INPUT_FORMATS:
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before conversion")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams) -> str:
        if encoding.format:
            return encoding.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        default_video_codec, _ = _FORMAT_CODEC_MAP.get(encoding.format or _DEFAULT_FORMAT, (None, None))
        return default_video_codec

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        _, default_audio_codec = _FORMAT_CODEC_MAP.get(encoding.format or _DEFAULT_FORMAT, (None, None))
        return default_audio_codec

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
