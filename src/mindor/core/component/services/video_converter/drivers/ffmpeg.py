from __future__ import annotations

from typing import Dict, List, Optional, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoConverterComponentConfig
from mindor.dsl.schema.action import VideoConverterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.ffmpeg.codecs import get_video_codecs_for_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import VideoConverterService, VideoConverterDriver, register_video_converter_service
from ..base import ComponentActionContext
from .common import VideoConverterAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

class FFmpegVideoConverterAction(VideoConverterAction):
    async def _convert_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        return await asyncio.gather(*[
            self._convert(video, params["encoding"], cancellation_token) for video in videos
        ])

    async def _convert(
        self,
        source: MediaSource,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = self._resolve_container_format(encoding)
        video, audio = encoding.video, encoding.audio

        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "video" ])
        is_streamable_output = is_streamable_video_format(format.lower())

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
        is_gif_format = (format == "gif")

        if video_codec:
            command.extend([ "-c:v", video_codec ])
        if video and video.bitrate and not is_gif_format:
            command.extend([ "-b:v", str(video.bitrate) ])
        if is_gif_format:
            # GIF has no audio track; palette filtering handles fps/resolution.
            command.extend([ "-an", "-filter_complex", self._build_gif_filter(video) ])
        else:
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
        output_path = get_temporary_path(format)
        is_gif_format = (format == "gif")

        if is_gif_format:
            command = command + [ "-y", output_path ]
        else:
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

    @staticmethod
    def _build_gif_filter(video: Optional[Any]) -> str:
        # palettegen/paletteuse produces a much higher-quality GIF than the default
        # 256-color web palette. fps and scale go in the filter graph so they compose
        # with the palette pass, instead of being applied by ffmpeg's global -r/-s.
        steps: List[str] = []

        if video and video.fps is not None:
            steps.append(f"fps={video.fps}")

        if video and video.resolution:
            width, _, height = video.resolution.partition("x")

            if width and height:
                steps.append(f"scale={width}:{height}:flags=lanczos")

        prefix = ",".join(steps) + "," if steps else ""

        return f"[0:v]{prefix}split[a][b];[a]palettegen[p];[b][p]paletteuse"

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams) -> str:
        if encoding.format:
            return encoding.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        video_codec, _ = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)
        return video_codec

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        _, audio_codec = get_video_codecs_for_format(encoding.format or _DEFAULT_FORMAT)
        return audio_codec

@register_video_converter_service(VideoConverterDriver.FFMPEG)
class FFmpegVideoConverterService(VideoConverterService):
    def __init__(self, id: str, config: VideoConverterComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoConverterActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoConverterAction(action).run(context)
