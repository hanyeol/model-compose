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
from mindor.core.utils.ffmpeg.muxer import get_extension_for_muxer, get_muxer_for_extension
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

            # When merging, cut each clip to an ISO-BMFF container (mp4/mov) so
            # concat sees stable per-clip A/V durations regardless of the final
            # output format. mpegts intermediates would silently drop audio at
            # the tail of every clip, and the drift would compound at each
            # concat seam. The final container is applied in the concat step.
            clip_format = await self._resolve_intermediate_format(input_path) if merge else format

            clips = self._clip(
                input_path,
                spooled,
                self._iterate_spans(spans),
                clip_format,
                precision,
                cancellation_token,
            )

            if merge:
                results.append(await self._merge(clips, clip_format, format, cancellation_token))
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

        # Fast mode snaps each span's start to the previous keyframe and its end
        # to the next keyframe, then cuts exactly those N video packets. The
        # returned span reflects what was actually cut. Requires a video stream
        # with keyframes; audio-only inputs (codec probe returns None) fall
        # through to the requested times unchanged.
        # `offset` is format.start_time (relative↔absolute pts shift). `keyframes`
        # is populated once (on the first miss) and reused for later spans;
        # indices within it are only meaningful within that one scan.
        keyframes: Optional[List[Tuple[float, int]]] = None
        offset: Optional[float] = None
        duration: Optional[float] = None

        if precision == VideoClipperPrecision.FAST:
            (codec, offset, duration) = await probe_video(input_path, ("codec", "start_time", "duration"))

            if codec is not None:
                offset = float(offset) if offset is not None else 0.0
            else:
                # Audio-only input: skip snap logic and let ffmpeg cut with the requested times.
                offset = None

        try:
            async for span in spans:
                start_time, end_time = span["start_time"], span["end_time"]
                frame_count: Optional[int] = None

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
                        start_time, end_time, frame_count, keyframes = await self._snap_to_keyframe(
                            input_path,
                            start_time,
                            end_time,
                            offset,
                            duration,
                            keyframes
                        )

                    # -ss / -t before -i seeks fast to the input keyframe; `-frames:v`
                    # stops at exactly N video packets, so B-frame decode-order lookahead
                    # can't leak an extra frame or two past the requested end keyframe.
                    # When frame_count is None the cut runs to end of file (no K2 found).
                    command = [
                        resolve_ffmpeg_executable(), "-hide_banner",
                        "-ss", f"{start_time:.6f}",
                        "-t", f"{(end_time - start_time):.6f}",
                        "-i", input_path,
                        "-c", "copy",
                    ]

                    if frame_count is not None:
                        command.extend([ "-frames:v", str(frame_count) ])

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
        clip_format: str,
        merge_format: str,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        """Concatenate an async stream of clips into a single video, carrying
        along each source span so callers can recover per-input positions.

        Each incoming clip is drained to a temp file (in `clip_format`) as it
        arrives; once the clip iterator is exhausted, ffmpeg's concat demuxer
        stitches them together with -c copy and remuxes into `merge_format`.
        Clips must share the same codec/container for -c copy to work —
        guaranteed here because they all come from the same _clip() call.

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
                clip_path = get_temporary_path(get_extension_for_muxer(clip_format))
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

            if is_streamable_video_format(merge_format):
                video = await self._run_to_stream(concat_command, merge_format, _cleanup, cancellation_token)
            else:
                video = await self._run_to_file(concat_command, merge_format, _cleanup, cancellation_token)

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
        command = command + [ "-f", get_muxer_for_extension(format), "pipe:1" ]
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
        end_time: float,
        offset: float,
        duration: Optional[float],
        keyframes: Optional[List[Tuple[float, int]]],
    ) -> Tuple[Optional[float], Optional[float], Optional[int], Optional[List[Tuple[float, int]]]]:
        """Return `(start_time_to_snap, end_time_to_snap, frame_count, keyframes)`.

        `start_time_to_snap` is the largest keyframe pts ≤ `start_time` in
        relative seconds; `end_time_to_snap` is the smallest keyframe pts ≥
        `end_time` (or `duration` when the request extends past the last
        keyframe). Both are None when no start keyframe was found — the caller
        then falls through to the requested times. `frame_count` is the number
        of video packets from the start keyframe up to (but not including) the
        end keyframe; feed it to `-frames:v` so B-frame decode-order lookahead
        can't leak past the end keyframe. None means cut to end of file.

        Tries a bounded pre-probe window covering both ends when `keyframes` is
        None; on miss (or when the window doesn't reach the file's end), falls
        back to a full-file scan. `keyframes` is handed back so later spans on
        the same input reuse it — packet indices are only meaningful within a
        single scan, so both endpoints must be resolved against the same list.
        """
        start_time = start_time + offset
        end_time   = end_time + offset

        if keyframes is None:
            window_start_time = start_time - _KEYFRAME_WINDOW_SECONDS
            window_end_time   = end_time   + _KEYFRAME_WINDOW_SECONDS

            # Use an open start when the window would begin at/before the file's
            # own start_time: some containers (mpegts) don't emit a boundary
            # keyframe otherwise.
            if window_start_time <= offset:
                window_start_time = None

            window_keyframes = await probe_video_keyframes(input_path, (window_start_time, window_end_time))
            start_keyframe = self._last_keyframe_before(window_keyframes, start_time)
            end_keyframe   = self._first_keyframe_after(window_keyframes, end_time)

            # A missing end entry is only OK when the file itself ends within
            # the window; otherwise the GOP is wider than the window and we
            # need a full scan.
            file_ends_in_window = duration is not None and window_end_time >= duration + offset

            if start_keyframe is None or (end_keyframe is None and not file_ends_in_window):
                # Window miss: fall back to a full scan and hand it back so
                # later spans on the same input can reuse it.
                keyframes = await probe_video_keyframes(input_path)
                start_keyframe = self._last_keyframe_before(keyframes, start_time)
                end_keyframe   = self._first_keyframe_after(keyframes, end_time)
            else:
                # Cache the window scan for later spans; indices remain valid
                # only because start/end entries came from this same scan.
                keyframes = window_keyframes
        else:
            start_keyframe = self._last_keyframe_before(keyframes, start_time)
            end_keyframe   = self._first_keyframe_after(keyframes, end_time)

        if start_keyframe is None:
            return None, None, None, keyframes

        # Convert absolute pts back to relative seconds. Ceil the start (so
        # ffmpeg's µs-quantized `-ss` lands on this keyframe, not the one
        # before) and floor the end (so `-t` doesn't reach into the next GOP);
        # the ≤1µs shift never crosses another keyframe boundary.
        start_pts, start_index = start_keyframe
        start_time = math.ceil((start_pts - offset) * 1_000_000) / 1_000_000

        if end_keyframe is None:
            return start_time, duration or end_time, None, keyframes

        end_pts, end_index = end_keyframe
        end_time = math.floor((end_pts - offset) * 1_000_000) / 1_000_000
        frame_count = end_index - start_index

        return start_time, end_time, frame_count, keyframes

    @staticmethod
    def _last_keyframe_before(keyframes: List[Tuple[float, int]], start_time: float) -> Optional[Tuple[float, int]]:
        """Return the `(pts, packet_index)` with the largest pts ≤ `start_time`, or None if no keyframe qualifies.

        Both `keyframes` and `start_time` must share a coordinate system (the
        caller handles absolute↔relative conversion).
        """
        keyframe: Optional[Tuple[float, int]] = None
        last_pts: float = -math.inf

        for pts, index in keyframes:
            if pts <= start_time and pts > last_pts:
                keyframe = (pts, index)
                last_pts = pts

        return keyframe

    @staticmethod
    def _first_keyframe_after(keyframes: List[Tuple[float, int]], end_time: float) -> Optional[Tuple[float, int]]:
        """Return the `(pts, packet_index)` with the smallest pts ≥ `end_time`, or None if no keyframe qualifies.

        Both `keyframes` and `end_time` must share a coordinate system (the
        caller handles absolute↔relative conversion).
        """
        keyframe: Optional[Tuple[float, int]] = None
        first_pts: float = math.inf

        for pts, index in keyframes:
            if pts >= end_time and pts < first_pts:
                keyframe = (pts, index)
                first_pts = pts

        return keyframe

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

    async def _resolve_intermediate_format(self, input_path: str) -> str:
        """Pick a per-clip container for merge intermediates.

        mp4 is the default (widest codec compatibility while keeping stable
        per-clip A/V durations); prores/dnxhd need mov instead since the mp4
        muxer refuses them. mkv is excluded because its 1ms timestamp
        quantization breaks the µs-precision keyframe snap.
        """
        (source_codec,) = await probe_video(input_path, ("codec",))

        if source_codec in ("prores", "dnxhd"):
            return "mov"

        return "mp4"

@register_video_clipper_driver(VideoClipperDriverType.FFMPEG)
class FFmpegVideoClipperService(VideoClipperDriver):
    def __init__(self, id: str, config: VideoClipperComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoClipperAction(action).run(context)
