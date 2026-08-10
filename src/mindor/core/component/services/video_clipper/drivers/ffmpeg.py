from __future__ import annotations

from typing import Optional, Union, Dict, List, Tuple, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoClipperComponentConfig
from mindor.dsl.schema.action import VideoClipperActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.files import create_temporary_file
from mindor.core.utils.video import is_streamable_video_format
from mindor.core.utils.ffmpeg import probe_container_format, get_extension_for_muxer
from mindor.core.utils.shell import run_subprocess, stream_subprocess
from mindor.core.logger import logging
from ..base import VideoClipperService, VideoClipperDriver, register_video_clipper_service
from ..base import ComponentActionContext
from .common import VideoClipperAction
import asyncio, os

class FFmpegVideoClipperAction(VideoClipperAction):
    async def _clip_batch(
        self,
        videos: List[MediaSource],
        spans: List[ArrayValue],
        merge: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[AsyncIterator[Dict[str, Any]], Dict[str, Any]]]:
        results: List[Union[AsyncIterator[Dict[str, Any]], Dict[str, Any]]] = []

        for video, spans in zip(videos, spans):
            input_path, spooled = await self._resolve_input_path(video)
            format = await self._resolve_format(video, input_path)

            clips = self._clip(
                input_path,
                spooled,
                self._iterate_spans(spans),
                format,
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

        try:
            async for span in spans:
                start_time = span["start_time"]
                end_time = span["end_time"]

                # -ss / -to before -i: fast input seek. With -c copy the cut aligns
                # to the nearest keyframe at/before start_time; both video and audio
                # streams are copied without re-encoding.
                command = [
                    "ffmpeg", "-hide_banner",
                    "-ss", f"{start_time:.6f}",
                    "-to", f"{end_time:.6f}",
                    "-i", input_path,
                    "-c", "copy",
                ]

                logging.debug(
                    "Clipping video [%s..%s] -> '%s'",
                    start_time, end_time, format,
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
                clip_path = create_temporary_file(get_extension_for_muxer(format))
                clip_paths.append(clip_path)
                times.append({ "start_time": clip["start_time"], "end_time": clip["end_time"] })

                with open(clip_path, "wb") as f:
                    async for chunk in clip["video"]:
                        f.write(chunk)

            if not clip_paths:
                return { "video": None, "times": [] }

            concat_list_path = create_temporary_file("txt")
            with open(concat_list_path, "w", encoding="utf-8") as f:
                for path in clip_paths:
                    # concat demuxer requires shell-safe paths; single-quote and escape any embedded quotes.
                    escaped = path.replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            concat_command = [
                "ffmpeg", "-hide_banner",
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
        output_path = create_temporary_file(get_extension_for_muxer(format))
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

    async def _resolve_input_path(self, source: MediaSource) -> Tuple[str, bool]:
        """
        Return a filesystem path ffmpeg can seek into for span cuts.

        Clipping runs one ffmpeg invocation per span with -ss/-to, so the input
        must support random access. pipe:0 is single-consumption and unusable
        here — any non-file source is spooled to a temp file first.

        - FileStreamResource: use its path directly (no spooling).
        - Otherwise: spool the stream to a temp file so ffmpeg can seek.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(source.stream, FileStreamResource):
            return source.stream.path, False

        logging.debug("ffmpeg input is not a file; spooling to a temp file before clipping")

        spooled_path = await save_stream_to_temporary_file(source.stream, source.format)

        return spooled_path, True

    async def _resolve_format(self, video: MediaSource, input_path: str) -> str:
        """Preserve the source format so `-c copy` produces a valid container.

        Prefers the caller-provided format hint on `video`, then the input
        file's extension, then falls back to ffprobe on the spooled/original
        file. ffprobe is only invoked when the first two fail, so the
        common cases pay no extra I/O.
        """
        if video.format:
            return video.format.lower()

        _, extension = os.path.splitext(input_path)

        if extension:
            return extension.lstrip(".").lower()

        return await probe_container_format(input_path)

@register_video_clipper_service(VideoClipperDriver.FFMPEG)
class FFmpegVideoClipperService(VideoClipperService):
    def __init__(self, id: str, config: VideoClipperComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoClipperActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoClipperAction(action).run(context)
