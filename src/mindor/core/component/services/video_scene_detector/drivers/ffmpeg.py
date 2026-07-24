from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Union, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.utils.shell import run_command, run_subprocess, stream_subprocess
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext
from .common import VideoSceneDetectorAction
import asyncio, json, os, re

_PTS_TIME_PATTERN = re.compile(rb"pts_time:\s*(\d+(?:\.\d+)?)")

class FFmpegVideoSceneDetectorAction(VideoSceneDetectorAction):
    async def _detect(
        self,
        video: MediaSource,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        input_path, spooled = await self._resolve_input_path(video)
        threshold = threshold if threshold is not None else 0.3

        command: List[str] = [ "ffmpeg", "-hide_banner" ]

        if start_time is not None:
            command.extend([ "-ss", str(start_time) ])
        if end_time is not None:
            command.extend([ "-to", str(end_time) ])

        command.extend([ "-i", input_path ])
        command.extend([ "-vf", f"select='gt(scene,{threshold})',showinfo" ])
        command.extend([ "-f", "null", "-" ])

        logging.debug(
            "Detecting scenes with ffmpeg (threshold=%s, streaming=%s)",
            threshold, streaming,
        )

        def _cleanup() -> None:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        duration   = await self._get_duration(input_path)
        frame_rate = await self._get_frame_rate(input_path)

        if streaming:
            return self._stream_scenes(command, duration, frame_rate, _cleanup, cancellation_token)

        return await self._collect_scenes(command, duration, frame_rate, _cleanup, cancellation_token)

    async def _collect_scenes(
        self,
        command: List[str],
        duration: float,
        frame_rate: float,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        """Run ffmpeg to completion and assemble the per-video scene result."""
        async def _handle_stderr(reader: asyncio.StreamReader) -> Tuple[List[float], bytes]:
            timestamps: List[float] = []
            error_lines: List[bytes] = []

            while True:
                line = await reader.readline()

                if not line:
                    break

                match = _PTS_TIME_PATTERN.search(line)

                if match:
                    timestamps.append(float(match.group(1)))
                else:
                    error_lines.append(line)

            return timestamps, b"".join(error_lines)

        # run_subprocess only reacts to asyncio cancellation, but our
        # CancellationToken is a threading.Event that has to be polled.
        # Wrap the ffmpeg run in a task and cancel it when the token fires;
        # run_subprocess then kills the process on its way out.
        process_task = asyncio.create_task(run_subprocess(
            command,
            stderr_handler=_handle_stderr,
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
            process, _, (timestamps, error) = await process_task

            if process.returncode != 0:
                error_message = error.decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg scene detection failed (exit code {process.returncode}): {error_message}")

            scenes: List[Dict[str, Any]] = []
            boundaries = [ 0.0 ] + timestamps + [ duration ]

            for index in range(len(boundaries) - 1):
                start = boundaries[index]
                end = boundaries[index + 1]
                scenes.append({
                    "index": index,
                    "start": format_timecode(start),
                    "end": format_timecode(end),
                    "start_frame": int(start * frame_rate),
                    "end_frame": int(end * frame_rate),
                    "duration": format_timecode(end - start)
                })

            return scenes
        except asyncio.CancelledError:
            logging.info("Scene detection cancelled")
            raise
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

    async def _stream_scenes(
        self,
        command: List[str],
        duration: float,
        frame_rate: float,
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Run ffmpeg and yield scene dicts as boundaries are detected."""
        timestamps: asyncio.Queue = asyncio.Queue()

        async def _handle_stderr(reader: asyncio.StreamReader) -> bytes:
            error_lines: List[bytes] = []

            while True:
                line = await reader.readline()

                if not line:
                    break

                match = _PTS_TIME_PATTERN.search(line)

                if match:
                    await timestamps.put(float(match.group(1)))
                else:
                    error_lines.append(line)

            await timestamps.put(None)  # sentinel: no more timestamps

            return b"".join(error_lines)

        watcher_task: Optional[asyncio.Task] = None

        try:
            async with stream_subprocess(
                command,
                stderr_handler=_handle_stderr,
            ) as (process, _, error):
                if cancellation_token is not None:
                    async def _watch_cancellation() -> None:
                        while not cancellation_token.is_cancelled():
                            if process.returncode is not None:
                                return
                            await asyncio.sleep(0.2)
                        process.kill()

                    watcher_task = asyncio.create_task(_watch_cancellation())

                index = 0
                prev_boundary = 0.0

                while True:
                    timestamp = await timestamps.get()
                    end = timestamp if timestamp is not None else duration

                    yield {
                        "index": index,
                        "start": format_timecode(prev_boundary),
                        "end": format_timecode(end),
                        "start_frame": int(prev_boundary * frame_rate),
                        "end_frame": int(end * frame_rate),
                        "duration": format_timecode(end - prev_boundary),
                    }

                    if timestamp is None:
                        break

                    index += 1
                    prev_boundary = timestamp

            if process.returncode is not None and process.returncode != 0:
                error_message = error.result().decode("utf-8", errors="replace") if error else ""
                raise RuntimeError(f"ffmpeg scene detection failed (exit code {process.returncode}): {error_message}")
        finally:
            if watcher_task is not None and not watcher_task.done():
                watcher_task.cancel()
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass

            cleanup()

    async def _resolve_input_path(self, video: MediaSource) -> Tuple[str, bool]:
        """
        Scene detection needs ffprobe metadata (duration, frame_rate) and seekable input,
        so we always end up with an on-disk path.

        - FileStreamResource: use its path directly (no spooling).
        - Otherwise: spool the stream to a temp file.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(video.stream, FileStreamResource):
            return video.stream.path, False

        logging.debug("Spooling video stream to a temp file before scene detection")

        spooled_path = await save_stream_to_temporary_file(video.stream, video.format)

        return spooled_path, True

    async def _get_frame_rate(self, video_path: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-select_streams", "v:0", "-show_streams", video_path,
        ]

        stdout, _, returncode = await run_command(command)

        if returncode != 0:
            raise RuntimeError(f"ffprobe failed to read frame rate (exit code {returncode})")

        result = json.loads(stdout.decode("utf-8"))
        frame_rate = result["streams"][0].get("r_frame_rate", "30/1")
        numerator, denominator = frame_rate.split("/")

        return float(numerator) / float(denominator)

    async def _get_duration(self, video_path: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video_path,
        ]

        stdout, _, returncode = await run_command(command)

        if returncode != 0:
            raise RuntimeError(f"ffprobe failed to read duration (exit code {returncode})")

        result = json.loads(stdout.decode("utf-8"))
        return float(result["format"]["duration"])

@register_video_scene_detector_service(VideoSceneDetectorDriver.FFMPEG)
class FFmpegVideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await FFmpegVideoSceneDetectorAction(action).run(context, loop)
