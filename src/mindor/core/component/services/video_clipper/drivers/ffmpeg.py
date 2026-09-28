from __future__ import annotations

from typing import Optional, Union, Dict, List, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoClipperComponentConfig
from mindor.dsl.schema.action import VideoClipperActionConfig, VideoClipperPrecision
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.ffmpeg.codecs import get_video_codecs_for_format
from mindor.core.utils.ffmpeg.executable import resolve_ffmpeg_executable
from mindor.core.utils.ffmpeg.probe import probe_video, probe_video_keyframes
from mindor.core.utils.ffmpeg.muxer import get_extension_for_muxer
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.files import get_temporary_path
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ....action.media import MediaInputPathResolver
from ..base import VideoClipperDriver, VideoClipperDriverType, register_video_clipper_driver
from ..base import ComponentActionContext
from .common import VideoClipperAction
import asyncio, math, os

# Initial pre-probe window (seconds) when locating a keyframe at/before a span
# start. If the window contains no keyframe (long GOP), we fall back to a full
# scan; the intermediate 60s tier is skipped because a window miss already
# means the file's GOP is unusual, and packet demuxing without decoding makes a
# full scan cheap enough on typical inputs.
_KEYFRAME_WINDOW_SECONDS = 10.0

class FFmpegVideoClipperAction(VideoClipperAction):
    async def _clip_batch(
        self,
        videos: List[MediaSource],
        spans: List[ArrayValue],
        merge: bool,
        precision: VideoClipperPrecision,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[AsyncIterator[Dict[str, Any]], Dict[str, Any]]]:
        results: List[Union[AsyncIterator[Dict[str, Any]], Dict[str, Any]]] = []

        for video, spans in zip(videos, spans):
            input_path, spooled = await MediaInputPathResolver().resolve(video)
            format = video.format.lower() if video.format else await self._resolve_format(input_path)

            clips = self._clip(
                input_path,
                spooled,
                self._iterate_spans(spans),
                format,
                precision,
                cancellation_token,
            )

            if merge:
                results.append(await self._merge(clips, format, cancellation_token))
            else:
                results.append(clips)

        return results

    async def _clip(
        self,
        input_path: str,
        spooled: bool,
        spans: AsyncIterator[Dict[str, float]],
        format: str,
        precision: VideoClipperPrecision,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Yield one VideoStreamResource per span, seeking into a shared input file.

        The input has already been materialized to a file by the caller so each
        span can seek independently. If the file was spooled by the caller
        (spooled=True), this method takes ownership of its cleanup: a refcount
        incremented per yielded clip is decremented when that clip's stream is
        fully consumed (or the process errors out); the last release deletes it.
        """
        # Every yielded clip's ffmpeg process reads from `input_path` in the
        # background, so we can only remove the spool once all of them are done.
        pending_count = 0
        released = False

        def _release() -> None:
            nonlocal pending_count, released

            pending_count -= 1
            if pending_count == 0 and released and spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        # Fast mode snaps each span's start to the nearest keyframe at/before it,
        # so the returned span reflects what was actually cut. Requires a video
        # stream with keyframes; input with no video track (or all-intra codecs
        # where every frame is a keyframe) falls through to the requested times.
        # `offset` is the input's format.start_time (relative↔absolute pts shift);
        # None means fast-mode snapping isn't applicable. `keyframes` starts empty
        # and is populated once (by the first window miss) then reused per span.
        keyframes: Optional[List[float]] = None
        offset: Optional[float] = None

        if precision == VideoClipperPrecision.FAST:
            offset = await self._resolve_start_time(input_path)

        try:
            async for span in spans:
                start_time = span["start_time"]
                end_time   = span["end_time"]

                if precision == VideoClipperPrecision.ACCURATE:
                    # -ss/-to after -i forces frame-accurate seek; re-encode with
                    # the source codecs so the container/pixel format keeps working.
                    video_codec, audio_codec = await self._resolve_codecs(input_path, format)

                    command = [
                        resolve_ffmpeg_executable(), "-hide_banner",
                        "-i", input_path,
                        "-ss", f"{start_time:.6f}",
                        "-to", f"{end_time:.6f}",
                        "-c:v", video_codec,
                    ]

                    if audio_codec is not None:
                        command.extend([ "-c:a", audio_codec ])
                else:
                    if offset is not None:
                        time_to_snap, keyframes = await self._snap_to_keyframe(input_path, start_time, offset, keyframes)

                        if time_to_snap is not None:
                            start_time = time_to_snap

                    # -ss / -to before -i: fast input seek. With -c copy the cut aligns
                    # to a keyframe; when we've pre-probed one, -ss lands exactly on it
                    # and no container-dependent lead-in frames leak into the output.
                    command = [
                        resolve_ffmpeg_executable(), "-hide_banner",
                        "-ss", f"{start_time:.6f}",
                        "-to", f"{end_time:.6f}",
                        "-i", input_path,
                        "-c", "copy",
                    ]

                logging.debug(
                    "Clipping video [%s..%s] (%s) -> '%s'",
                    start_time, end_time, precision.value, format,
                )

                pending_count += 1

                try:
                    if is_streamable_video_format(format):
                        clip = await self._run_to_stream(command, format, _release, cancellation_token)
                    else:
                        clip = await self._run_to_file(command, format, _release, cancellation_token)
                except BaseException:
                    # cleanup wasn't invoked on this iteration; roll back the refcount.
                    pending_count -= 1
                    raise

                yield { "video": clip, "start_time": start_time, "end_time": end_time }
        finally:
            # After the span iterator is exhausted, allow the last clip's cleanup
            # to remove the spool file. If no clips remain in flight, remove it now.
            released = True
            if pending_count == 0 and spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    async def _merge(
        self,
        clips: AsyncIterator[Dict[str, Any]],
        format: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Concatenate an async stream of clips into a single video, carrying
        along each source span so callers can recover per-input positions.

        Each incoming clip is drained to a temp file as it arrives; once the
        clip iterator is exhausted, ffmpeg's concat demuxer stitches the files
        together with -c copy (no re-encoding). Clips must share the same
        codec/container for -c copy to work — that's guaranteed here because
        they all come from the same _clip() call.

        Returns `{video, times: [{start_time, end_time}, ...]}`; when the clip
        iterator produced nothing, `video` is None and `times` is empty.
        """
        clip_paths: List[str] = []
        times: List[Dict[str, float]] = []
        concat_list_path: Optional[str] = None

        def _cleanup() -> None:
            for path in clip_paths:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
            if concat_list_path is not None:
                try:
                    os.remove(concat_list_path)
                except FileNotFoundError:
                    pass

        try:
            async for clip in clips:
                clip_path = get_temporary_path(get_extension_for_muxer(format))
                clip_paths.append(clip_path)
                times.append({ "start_time": clip["start_time"], "end_time": clip["end_time"] })

                with open(clip_path, "wb") as f:
                    async for chunk in clip["video"]:
                        f.write(chunk)

            if not clip_paths:
                return { "video": None, "times": [] }

            concat_list_path = get_temporary_path("txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for path in clip_paths:
                    # concat demuxer requires shell-safe paths; single-quote and escape any embedded quotes.
                    escaped = path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            concat_command = [
                resolve_ffmpeg_executable(), "-hide_banner",
                "-f", "concat", "-safe", "0",
                "-i", concat_list_path,
                "-c", "copy",
            ]

            if is_streamable_video_format(format):
                video = await self._run_to_stream(concat_command, format, _cleanup, cancellation_token)
            else:
                video = await self._run_to_file(concat_command, format, _cleanup, cancellation_token)

            return { "video": video, "times": times }
        except BaseException:
            _cleanup()
            raise

    async def _run_to_file(
        self,
        command: List[str],
        format: str,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> VideoStreamResource:
        """Run ffmpeg to a temporary file, then return a VideoStreamResource over that file."""
        output_path = get_temporary_path(get_extension_for_muxer(format))
        command = command + [ "-y", output_path ]

        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            None,
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
            try:
                process, _, error = await process_task

                if process.returncode != 0:
                    error_message = error.decode("utf-8", errors="replace") if error else ""
                    raise RuntimeError(f"ffmpeg video clip failed (exit code {process.returncode}): {error_message}")
            except asyncio.CancelledError:
                logging.info("Video clip cancelled")
                raise
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass
        except BaseException:
            cleanup()
            raise

        cleanup()

        logging.debug("Video clip completed: '%s'", output_path)

        return VideoStreamResource(FileStreamResource(output_path, auto_delete=True), format=format)

    async def _run_to_stream(
        self,
        command: list,
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
                    source=None,
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
                    raise RuntimeError(f"ffmpeg video clipping failed (exit code {process.returncode}): {error_message}")
            finally:
                if watcher_task is not None and not watcher_task.done():
                    watcher_task.cancel()
                    try:
                        await watcher_task
                    except (asyncio.CancelledError, Exception):
                        pass

                cleanup()

        return VideoStreamResource(AsyncIterableStreamResource(_stream()), format=format)

    async def _snap_to_keyframe(
        self,
        input_path: str,
        start_time: float,
        offset: float,
        keyframes: Optional[List[float]],
    ) -> Tuple[Optional[float], Optional[List[float]]]:
        """Return `(time_to_snap, keyframes)`.

        `time_to_snap` is the largest keyframe pts ≤ `start_time` in
        relative seconds, or None if no such keyframe was found. `keyframes` is
        the full-file keyframe list (absolute pts) when a full scan was needed,
        or the value passed in — callers should reuse it for subsequent spans
        to skip re-probing.

        Tries a bounded pre-probe window first for cheap access when `keyframes`
        is None; on miss, escalates to a full-file scan.
        """
        start_time = start_time + offset

        if keyframes is None:
            window_start: Optional[float] = start_time - _KEYFRAME_WINDOW_SECONDS

            # Use an open start when the window would begin at/before the file's
            # own start_time: some containers (mpegts) don't emit a boundary
            # keyframe otherwise.
            if window_start <= offset:
                window_start = None

            # ffprobe's `-read_intervals` treats the end as exclusive, so a
            # keyframe sitting exactly at `start_time` would be missed; bump the
            # end by a small epsilon (well under one frame) to include it.
            windowed = await probe_video_keyframes(input_path, (window_start, start_time + 1e-3))
            time_to_snap = self._last_keyframe_time_before(windowed, start_time)

            if time_to_snap is None:
                # Window miss: fall back to a full scan and hand it back so
                # later spans on the same input can reuse it.
                keyframes = await probe_video_keyframes(input_path)
                time_to_snap = self._last_keyframe_time_before(keyframes, start_time)
        else:
            time_to_snap = self._last_keyframe_time_before(keyframes, start_time)

        if time_to_snap is None:
            return None, keyframes

        # Convert absolute pts back to relative seconds and round up to the nearest
        # microsecond so ffmpeg's µs-quantized `-ss` lands on this keyframe rather
        # than the previous one; the ≤1µs shift never crosses another keyframe boundary.
        start_time = math.ceil((time_to_snap - offset) * 1_000_000) / 1_000_000

        return start_time, keyframes

    @staticmethod
    def _last_keyframe_time_before(keyframes: List[float], start: float) -> Optional[float]:
        """Return the largest keyframe pts ≤ `start`, or None if no keyframe qualifies.

        Both `keyframes` and `start` must share a coordinate system (the caller
        handles absolute↔relative conversion).
        """
        candidate: Optional[float] = None

        for pts in keyframes:
            if pts <= start and (candidate is None or pts > candidate):
                candidate = pts

        return candidate

    async def _resolve_start_time(self, input_path: str) -> Optional[float]:
        """Return the video's `format.start_time` (0.0 when absent), or None
        when the input has no video stream.

        Callers use the offset to convert between the caller's relative seek
        times and ffprobe's absolute pts; a None return signals fast-mode
        snapping isn't applicable and the caller should fall through to the
        requested times.
        """
        (codec, offset) = await probe_video(input_path, ("codec", "start_time"))

        if codec is None:
            return None

        return float(offset) if offset is not None else 0.0

    async def _resolve_codecs(self, input_path: str, format: str) -> Tuple[str, Optional[str]]:
        """Pick (video, audio) codecs for the output.

        Prefers the input's own codec so the output container/pixel format keeps
        working without extra conversion. Falls back to the container's default
        pairing (from `codecs.get_video_codecs_for_format`) when the source codec
        is unknown or unset — same policy other drivers use for encoding.
        """
        (source_codec,) = await probe_video(input_path, ("codec",))
        video_default, audio_default = get_video_codecs_for_format(format)
        video_codec = source_codec or video_default or "libx264"

        return video_codec, audio_default

    async def _resolve_format(self, input_path: str) -> str:
        """Determine the container format of an input file so `-c copy` produces a valid output.

        Order: the file extension, then ffprobe as a fallback. ffprobe is only
        invoked when the extension is missing, so the common case pays no extra I/O.
        """
        _, extension = os.path.splitext(input_path)

        if extension:
            return extension.lstrip(".").lower()

        (format,) = await probe_video(input_path, ("format",))

        return format

@register_video_clipper_driver(VideoClipperDriverType.FFMPEG)
class FFmpegVideoClipperService(VideoClipperDriver):
    def __init__(self, id: str, config: VideoClipperComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoClipperAction(action).run(context)
