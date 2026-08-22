from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoProcessorComponentConfig
from mindor.dsl.schema.action import (
    VideoProcessorActionConfig,
    VideoProcessorActionMethod,
    VideoScaleMode,
    VideoFlipDirection,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.logger import logging
from ..base import VideoProcessorService, VideoProcessorDriver, register_video_processor_service
from ..base import ComponentActionContext
from .common import VideoProcessorAction
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

class FFmpegVideoProcessorAction(VideoProcessorAction):
    async def _process_batch(
        self,
        method: VideoProcessorActionMethod,
        videos: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        return await asyncio.gather(*[
            self._process(method, video, params, cancellation_token) for video in videos
        ])

    async def _process(
        self,
        method: VideoProcessorActionMethod,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        encoding: VideoAudioEncodingParams = params["encoding"]
        format = self._resolve_container_format(encoding, source)
        video_encoder = encoding.video
        audio_encoder = encoding.audio

        input_path, spooled = await self._resolve_input_path(source)
        is_streamable_output = is_streamable_video_format(format.lower())

        command: List[str] = [ "ffmpeg", "-hide_banner" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])
        if source.attrs.get("resolution"):
            command.extend([ "-s", str(source.attrs["resolution"]) ])
        if source.attrs.get("fps"):
            command.extend([ "-r", str(source.attrs["fps"]) ])
        if source.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source.attrs["pixel_format"]) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])

        video_filter = self._build_video_filter(method, params)
        command.extend([ "-vf", video_filter ])

        video_codec = self._resolve_video_codec(encoding, format)
        audio_codec = self._resolve_audio_codec(encoding)

        if video_codec:
            command.extend([ "-c:v", video_codec ])
        if video_encoder and video_encoder.bitrate:
            command.extend([ "-b:v", str(video_encoder.bitrate) ])
        if audio_codec:
            command.extend([ "-c:a", audio_codec ])
        if audio_encoder and audio_encoder.bitrate:
            command.extend([ "-b:a", str(audio_encoder.bitrate) ])
        if video_encoder and video_encoder.resolution:
            command.extend([ "-s", video_encoder.resolution ])
        if video_encoder and video_encoder.fps is not None:
            command.extend([ "-r", str(video_encoder.fps) ])

        def _cleanup() -> None:
            if spooled and input_path is not None:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(
            "Processing video with '%s' (%s input, %s output, filter='%s')",
            method.value,
            "path" if input_path else "pipe",
            "stream" if is_streamable_output else "file",
            video_filter,
        )

        if is_streamable_output:
            return await self._process_to_stream(command, source, input_path, format, _cleanup, cancellation_token)

        return await self._process_to_file(command, source, input_path, format, _cleanup, cancellation_token)

    def _build_video_filter(self, method: VideoProcessorActionMethod, params: Dict[str, Any]) -> str:
        if method == VideoProcessorActionMethod.RESIZE:
            return self._build_resize_filter(params)

        if method == VideoProcessorActionMethod.CROP:
            return self._build_crop_filter(params)

        if method == VideoProcessorActionMethod.PAD:
            return self._build_pad_filter(params)

        if method == VideoProcessorActionMethod.FLIP:
            return self._build_flip_filter(params)

        if method == VideoProcessorActionMethod.ROTATE:
            return self._build_rotate_filter(params)

        raise ValueError(f"Unsupported video processing action method: {method}")

    def _build_resize_filter(self, params: Dict[str, Any]) -> str:
        width      = params["width"]
        height     = params["height"]
        scale_mode = params["scale_mode"]

        # ffmpeg's scale filter uses -1 to mean "preserve aspect ratio from the other axis".
        # scale=w:h uses stretch semantics by default; force_original_aspect_ratio adds fit/fill.
        target_w = str(width)  if width  is not None else "-2"
        target_h = str(height) if height is not None else "-2"

        if scale_mode == VideoScaleMode.STRETCH:
            return f"scale={target_w}:{target_h}"

        # For fit/fill both dimensions must be known; if only one is set the aspect-preserving
        # -2 already gives fit semantics, so we can short-circuit.
        if width is None or height is None:
            return f"scale={target_w}:{target_h}"

        if scale_mode == VideoScaleMode.FIT:
            # Fit inside the target box, then pad to exact size so downstream sees width x height.
            return (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0"
            )

        # FILL: cover the target box and center-crop the overflow.
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )

    def _build_crop_filter(self, params: Dict[str, Any]) -> str:
        return f"crop={params['width']}:{params['height']}:{params['x']}:{params['y']}"

    def _build_pad_filter(self, params: Dict[str, Any]) -> str:
        left, right, top, bottom = params["left"], params["right"], params["top"], params["bottom"]
        color = self._format_color(params["color"])

        # ffmpeg pad: pad=out_w:out_h:x:y where (x, y) is the top-left of the source inside the padded canvas.
        return f"pad=iw+{left + right}:ih+{top + bottom}:{left}:{top}:color={color}"

    def _build_flip_filter(self, params: Dict[str, Any]) -> str:
        if params["direction"] == VideoFlipDirection.HORIZONTAL:
            return "hflip"

        return "vflip"

    def _build_rotate_filter(self, params: Dict[str, Any]) -> str:
        angle = params["angle"]
        # ffmpeg's rotate filter takes radians and rotates clockwise; our schema follows
        # image_processor's counter-clockwise degrees convention, so negate.
        import math
        radians = -math.radians(angle)

        if params["expand"]:
            # Grow the output canvas to fit the rotated frame (transparent background).
            return (
                f"rotate={radians}:"
                f"ow='hypot(iw,ih)':oh='hypot(iw,ih)':"
                f"c=none"
            )

        return f"rotate={radians}"

    async def _process_to_file(
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

        command = command + [ "-movflags", "+faststart", "-y", output_path ]

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
                raise RuntimeError(f"ffmpeg video processing failed (exit code {process.returncode}): {error_message}")
        except asyncio.CancelledError:
            logging.info("Video processing cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

        logging.debug("Video processing completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _process_to_stream(
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
                    raise RuntimeError(f"ffmpeg video processing failed (exit code {process.returncode}): {error_message}")
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

        if is_streamable_video_format(source.format):
            return None, False

        logging.debug("ffmpeg input is not streamable; spooling to a temp file before processing")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    @staticmethod
    def _resolve_container_format(encoding: VideoAudioEncodingParams, source: MediaSource) -> str:
        # Priority: explicit encoding.format > source.format > default (mp4).
        # Applying a video filter forces re-encode, so the container just needs
        # to be something ffmpeg can mux the resulting streams into.
        if encoding.format:
            return encoding.format.lower()

        if source.format:
            return source.format.lower()

        return _DEFAULT_FORMAT

    @staticmethod
    def _resolve_video_codec(encoding: VideoAudioEncodingParams, format: str) -> Optional[str]:
        # Filter graphs decode frames, so we always re-encode the video track;
        # -c:v copy is not a valid option here. Fall back to the container default.
        if encoding.video and encoding.video.codec:
            return encoding.video.codec

        default_video_codec, _ = _FORMAT_CODEC_MAP.get(format, (None, None))
        return default_video_codec

    @staticmethod
    def _resolve_audio_codec(encoding: VideoAudioEncodingParams) -> Optional[str]:
        # Filters only touch the video stream, so we can stream-copy audio when
        # the user hasn't asked for anything specific.
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        return "copy"

    @staticmethod
    def _format_color(color: Any) -> str:
        if isinstance(color, str):
            return color

        if isinstance(color, (list, tuple)):
            if len(color) == 4:
                r, g, b, a = color
                return f"0x{r:02X}{g:02X}{b:02X}{a:02X}"
            if len(color) == 3:
                r, g, b = color
                return f"0x{r:02X}{g:02X}{b:02X}"

        return "black@0"

@register_video_processor_service(VideoProcessorDriver.FFMPEG)
class FFmpegVideoProcessorService(VideoProcessorService):
    def __init__(self, id: str, config: VideoProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoProcessorAction(action).run(context)
