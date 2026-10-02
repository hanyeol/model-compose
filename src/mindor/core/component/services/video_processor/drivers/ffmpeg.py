from __future__ import annotations

from typing import List, Optional, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoProcessorComponentConfig
from mindor.dsl.schema.action import (
    VideoProcessorActionConfig,
    VideoScaleMode,
    VideoFlipDirection,
    VideoFreezePosition,
)
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.media.encoding import VideoAudioEncodingParams
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from mindor.core.utils.ffmpeg.codecs import get_video_codecs_for_format
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import VideoProcessorDriver, VideoProcessorDriverType, register_video_processor_driver
from ..base import ComponentActionContext
from .common import VideoProcessorAction
import asyncio, os

_DEFAULT_FORMAT = "mp4"

class FFmpegVideoProcessorAction(VideoProcessorAction):
    async def _resize(
        self,
        video: MediaSource,
        width: Optional[int],
        height: Optional[int],
        scale_mode: VideoScaleMode,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # ffmpeg's scale filter uses -1 to mean "preserve aspect ratio from the other axis".
        # scale=w:h uses stretch semantics by default; force_original_aspect_ratio adds fit/fill.
        target_w = str(width)  if width  is not None else "-2"
        target_h = str(height) if height is not None else "-2"

        if scale_mode == VideoScaleMode.STRETCH:
            video_filter = f"scale={target_w}:{target_h}"
        elif width is None or height is None:
            # For fit/fill both dimensions must be known; if only one is set the aspect-preserving
            # -2 already gives fit semantics, so we can short-circuit.
            video_filter = f"scale={target_w}:{target_h}"
        elif scale_mode == VideoScaleMode.FIT:
            # Fit inside the target box, then pad to exact size so downstream sees width x height.
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black@0"
            )
        else:
            # FILL: cover the target box and center-crop the overflow.
            video_filter = (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )

        return await self._run_ffmpeg_filter(video, video_filter, None, encoding, cancellation_token)

    async def _crop(
        self,
        video: MediaSource,
        x: int,
        y: int,
        width: int,
        height: int,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        video_filter = f"crop={width}:{height}:{x}:{y}"

        return await self._run_ffmpeg_filter(video, video_filter, None, encoding, cancellation_token)

    async def _pad(
        self,
        video: MediaSource,
        left: int,
        right: int,
        top: int,
        bottom: int,
        color: Any,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        video_filter = f"pad=iw+{left + right}:ih+{top + bottom}:{left}:{top}:color={self._format_color(color)}"

        return await self._run_ffmpeg_filter(video, video_filter, None, encoding, cancellation_token)

    async def _flip(
        self,
        video: MediaSource,
        direction: VideoFlipDirection,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        video_filter = "hflip" if direction == VideoFlipDirection.HORIZONTAL else "vflip"

        return await self._run_ffmpeg_filter(video, video_filter, None, encoding, cancellation_token)

    async def _rotate(
        self,
        video: MediaSource,
        angle: float,
        expand: bool,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        import math

        # Our schema follows image_processor's counter-clockwise degrees
        # convention. Multiples of 90° are handled by `transpose`/`hflip`
        # rather than `rotate` — no resampling, no fill colour, and the
        # dimensions are exact (swapped for 90/270). Everything else falls
        # through to the generic `rotate` path below.
        right_angle_filters = self._right_angle_rotate_filter(angle)

        if right_angle_filters is not None:
            return await self._run_ffmpeg_filter(video, right_angle_filters, None, encoding, cancellation_token)

        # ffmpeg's rotate filter takes radians and rotates clockwise, so
        # negate to match the counter-clockwise convention.
        radians = -math.radians(angle)

        if expand:
            # Grow the output canvas to the rotated bounding box using
            # `rotw(a)`/`roth(a)` — the true rotated size, not a hypot-sized
            # square that leaves triangular black corners. Round up to even
            # pixels because yuv420p demands even dimensions. `c=black` makes
            # the fill explicit; the previous `c=none` implied transparency
            # but only produces alpha when the output container carries it,
            # and shows as black on yuv420p output.
            video_filter = (
                f"rotate={radians}:"
                f"ow='2*ceil(rotw({radians})/2)':oh='2*ceil(roth({radians})/2)':"
                f"c=black"
            )
        else:
            video_filter = f"rotate={radians}"

        return await self._run_ffmpeg_filter(video, video_filter, None, encoding, cancellation_token)

    async def _speed(
        self,
        video: MediaSource,
        speed: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # Video: setpts scales presentation timestamps — 1/speed speeds playback up.
        # Audio: atempo preserves pitch, but each stage only accepts 0.5..2.0, so
        # chain multiple stages for speeds outside that band to keep A/V in sync.
        video_filter = f"setpts={1.0 / speed}*PTS"
        audio_filter = self._build_atempo_chain(speed)

        return await self._run_ffmpeg_filter(video, video_filter, audio_filter, encoding, cancellation_token)

    async def _fade_in(
        self,
        video: MediaSource,
        start_time: float,
        duration: float,
        color: Any,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # `fade=t=in` blends from `color` into the source; `afade=t=in` mirrors
        # it on the audio so a silent lead-in matches the visual reveal.
        video_filter = f"fade=t=in:st={start_time}:d={duration}:color={self._format_color(color)}"
        audio_filter = f"afade=t=in:st={start_time}:d={duration}"

        return await self._run_ffmpeg_filter(video, video_filter, audio_filter, encoding, cancellation_token)

    async def _fade_out(
        self,
        video: MediaSource,
        start_time: float,
        duration: float,
        color: Any,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        video_filter = f"fade=t=out:st={start_time}:d={duration}:color={self._format_color(color)}"
        audio_filter = f"afade=t=out:st={start_time}:d={duration}"

        return await self._run_ffmpeg_filter(video, video_filter, audio_filter, encoding, cancellation_token)

    async def _freeze(
        self,
        video: MediaSource,
        position: VideoFreezePosition,
        duration: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # `tpad` clones the first/last frame to hold it for `duration` seconds.
        # Audio is padded with silence via `apad=pad_dur` on the matching end
        # so the audio track stays in sync with the extended video.
        if position == VideoFreezePosition.START:
            video_filter = f"tpad=start_duration={duration}:start_mode=clone"
            audio_filter = f"adelay={int(duration * 1000)}:all=1"
        else:
            video_filter = f"tpad=stop_duration={duration}:stop_mode=clone"
            audio_filter = f"apad=pad_dur={duration}"

        return await self._run_ffmpeg_filter(video, video_filter, audio_filter, encoding, cancellation_token)

    async def _reverse(
        self,
        video: MediaSource,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # `reverse` buffers the entire stream in memory — fine for short clips,
        # but callers should trim first for long sources. `areverse` mirrors
        # the audio so playback stays in sync end-to-end.
        return await self._run_ffmpeg_filter(video, "reverse", "areverse", encoding, cancellation_token)

    async def _resample(
        self,
        video: MediaSource,
        fps: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"fps={fps}", None, encoding, cancellation_token)

    async def _adjust_color(
        self,
        video: MediaSource,
        brightness: Optional[float],
        contrast: Optional[float],
        saturation: Optional[float],
        gamma: Optional[float],
        hue: Optional[float],
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        # Order matches image-processor so results stay comparable: brightness
        # (curves, true multiplier like PIL) → contrast/saturation/gamma (eq,
        # all natively multipliers in ffmpeg) → hue rotation.
        chain: List[str] = []

        if brightness is not None:
            chain.append(f"curves=all='0/0 1/{brightness}'")

        eq_terms: List[str] = []

        if contrast is not None:
            eq_terms.append(f"contrast={contrast}")

        if saturation is not None:
            eq_terms.append(f"saturation={saturation}")

        if gamma is not None:
            eq_terms.append(f"gamma={gamma}")

        if eq_terms:
            chain.append("eq=" + ":".join(eq_terms))

        if hue is not None:
            chain.append(f"hue=h={hue}")

        return await self._run_ffmpeg_filter(video, ",".join(chain), None, encoding, cancellation_token)

    async def _adjust_brightness(
        self,
        video: MediaSource,
        factor: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"curves=all='0/0 1/{factor}'", None, encoding, cancellation_token)

    async def _adjust_contrast(
        self,
        video: MediaSource,
        factor: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"eq=contrast={factor}", None, encoding, cancellation_token)

    async def _adjust_saturation(
        self,
        video: MediaSource,
        factor: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"eq=saturation={factor}", None, encoding, cancellation_token)

    async def _adjust_gamma(
        self,
        video: MediaSource,
        gamma: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"eq=gamma={gamma}", None, encoding, cancellation_token)

    async def _adjust_hue(
        self,
        video: MediaSource,
        hue: float,
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        return await self._run_ffmpeg_filter(video, f"hue=h={hue}", None, encoding, cancellation_token)

    async def _run_ffmpeg_filter(
        self,
        source: MediaSource,
        video_filter: str,
        audio_filter: Optional[str],
        encoding: VideoAudioEncodingParams,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        format = self._resolve_container_format(encoding, source)
        video_encoder = encoding.video
        audio_encoder = encoding.audio

        input_path, spooled = await MediaInputPathResolver().resolve(source, streamable_media=[ "video" ])
        is_streamable_output = is_streamable_video_format(format.lower())

        command: List[str] = [ resolve_ffmpeg_executable(), "-hide_banner" ]

        if source.format and input_path is None:
            command.extend([ "-f", source.format ])
        if source.attrs.get("resolution"):
            command.extend([ "-s", str(source.attrs["resolution"]) ])
        if source.attrs.get("fps"):
            command.extend([ "-r", str(source.attrs["fps"]) ])
        if source.attrs.get("pixel_format"):
            command.extend([ "-pix_fmt", str(source.attrs["pixel_format"]) ])

        command.extend([ "-i", input_path if input_path is not None else "pipe:0" ])
        command.extend([ "-vf", video_filter ])

        if audio_filter is not None:
            command.extend([ "-af", audio_filter ])

        video_codec = self._resolve_video_codec(encoding, format)
        # An audio filter forces re-encoding the audio stream (copy is invalid then).
        audio_codec = self._resolve_audio_codec(encoding, force_reencode=audio_filter is not None, format=format)

        if video_codec:
            command.extend([ "-c:v", video_codec ])
        if video_encoder and video_encoder.quality is not None:
            command.extend([ "-crf", str(video_encoder.quality) ])
        elif video_encoder and video_encoder.bitrate:
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
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        logging.debug(
            "Processing video (%s input, %s output, filter='%s')",
            "path" if input_path else "pipe",
            "stream" if is_streamable_output else "file",
            video_filter,
        )

        if is_streamable_output:
            return await self._process_to_stream(command, source, input_path, format, _cleanup, cancellation_token)

        return await self._process_to_file(command, source, input_path, format, _cleanup, cancellation_token)

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

        video_codec, _ = get_video_codecs_for_format(format)

        return video_codec

    @staticmethod
    def _resolve_audio_codec(
        encoding: VideoAudioEncodingParams,
        force_reencode: bool = False,
        format: Optional[str] = None,
    ) -> Optional[str]:
        # Filters only touch the video stream, so we can stream-copy audio when
        # the user hasn't asked for anything specific. When an audio filter is
        # applied (e.g. atempo for `speed`), stream-copy is not valid — fall back
        # to the container's default audio codec.
        if encoding.audio and encoding.audio.codec:
            return encoding.audio.codec

        if force_reencode:
            _, audio_codec = get_video_codecs_for_format(format or _DEFAULT_FORMAT)
            return audio_codec

        return "copy"

    @staticmethod
    def _build_atempo_chain(speed: float) -> str:
        atempo = speed
        stages: List[str] = []

        while atempo > 2.0:
            stages.append("atempo=2.0")
            atempo /= 2.0

        while atempo < 0.5:
            stages.append("atempo=0.5")
            atempo /= 0.5

        stages.append(f"atempo={atempo}")

        return ",".join(stages)

    @staticmethod
    def _right_angle_rotate_filter(angle: float) -> Optional[str]:
        """Return a `transpose`/`hflip` chain for multiples of 90°, or None.

        Angles are counter-clockwise degrees; ffmpeg's `transpose=1` is 90°
        clockwise, so the mapping inverts. Non-multiples fall through to the
        caller's generic `rotate` path.
        """
        angle = angle % 360

        if angle == 0:
            return "null"

        if angle == 90:
            return "transpose=2"

        if angle == 180:
            return "hflip,vflip"

        if angle == 270:
            return "transpose=1"

        return None

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

@register_video_processor_driver(VideoProcessorDriverType.FFMPEG)
class FFmpegVideoProcessorService(VideoProcessorDriver):
    def __init__(self, id: str, config: VideoProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoProcessorAction(action).run(context)
