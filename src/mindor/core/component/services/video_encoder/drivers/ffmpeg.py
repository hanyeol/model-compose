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
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from PIL import Image as PILImage
from ..base import VideoEncoderService, register_video_encoder_service
from ..base import ComponentActionContext
from .common import VideoEncoderAction
import asyncio, io, os

# Output container formats that can be written to ffmpeg's stdout (no post-write seek).
# Others (mp4/mov/mkv/avi/...) need a real file path with seeking — typically for moov atom
# placement, index tables, +faststart, etc.
_STREAMABLE_OUTPUT_FORMATS: Set[str] = {
    "mpegts", "ts", "flv", "ogg", "webm",
}

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

        video_path, video_spooled = await self._resolve_input_path(video)
        audio_path, audio_spooled = (None, False)

        if streaming and format.lower() not in _STREAMABLE_OUTPUT_FORMATS:
            logging.warning(f"Format '{format}' is not streamable; falling back to file output.")
            streaming = False

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

        for option, value in self._resolve_encoding_options(params, has_audio=audio_path is not None).items():
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

        logging.debug(f"Encoding video to '{format}'")

        if streaming:
            return await self._encode_to_stream(command, source_bytes, format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, source_bytes, format, _cleanup, cancellation_token)

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
        audio_path, audio_spooled = (None, False)

        if audio is not None:
            audio_path, audio_spooled = await self._resolve_input_path(audio)

        if streaming and format.lower() not in _STREAMABLE_OUTPUT_FORMATS:
            logging.warning(f"Format '{format}' is not streamable; falling back to file output.")
            streaming = False

        command = [ "ffmpeg", "-hide_banner", "-y" ]
        command.extend([ "-f", "image2pipe", "-framerate", str(frame_rate), "-i", "pipe:0" ])

        if audio_path is not None:
            command.extend([ "-i", audio_path ])
            command.extend([ "-map", "0:v", "-map", "1:a" ])

        for option, value in self._resolve_encoding_options(params, has_audio=audio_path is not None).items():
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

        logging.debug(f"Encoding {len(frames)} frames to '{format}'")

        if streaming:
            return await self._encode_to_stream(command, _frames_bytes(), format, _cleanup, cancellation_token)

        return await self._encode_to_file(command, _frames_bytes(), format, _cleanup, cancellation_token)

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
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = create_temporary_file(format)

        command = command + [ "-movflags", "+faststart", output_path ]

        try:
            process, _, error = await run_subprocess(
                command,
                source,
                stderr_handler=lambda r: r.read(),
            )

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
        finally:
            cleanup()

        logging.debug(f"Video encoding completed: '{output_path}'")

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _encode_to_stream(
        self,
        command: List[str],
        source: Optional[AsyncIterable[bytes]],
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
            try:
                async with stream_subprocess(
                    command,
                    source=source,
                    stdout_handler=_handle_stdout,
                    stderr_handler=_handle_stderr,
                ) as (process, chunks, _):
                    async for chunk in chunks:
                        yield chunk

                if process.returncode is not None and process.returncode != 0:
                    error_message = b"".join(error).decode("utf-8", errors="replace")
                    raise RuntimeError(f"ffmpeg video encoding failed (exit code {process.returncode}): {error_message}")
            finally:
                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[Optional[str], bool]:
        """Return a filesystem path for `source`, spooling to a temp file if needed.

        Returns (path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

@register_video_encoder_service(VideoEncoderDriver.FFMPEG)
class FFmpegVideoEncoderService(VideoEncoderService):
    def __init__(self, id: str, config: VideoEncoderComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoEncoderActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoEncoderAction(action).run(context, loop)
