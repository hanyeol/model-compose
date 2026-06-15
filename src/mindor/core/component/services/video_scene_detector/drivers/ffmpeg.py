from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.utils.shell import run_command, run_subprocess
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
        end_time: Optional[float]
    ) -> Dict[str, Any]:
        threshold = threshold if threshold is not None else 0.3
        input_path, spooled = await self._resolve_input_path(video)

        try:
            timestamps = await self._detect_scenes(input_path, threshold, start_time, end_time)
            duration   = await self._get_duration(input_path)
            frame_rate = await self._get_frame_rate(input_path)

            scenes: List[Dict[str, Any]] = []
            boundaries = [ 0.0 ] + timestamps + [ duration ]

            for i in range(len(boundaries) - 1):
                start = boundaries[i]
                end = boundaries[i + 1]
                scenes.append({
                    "index": i,
                    "start": format_timecode(start),
                    "end": format_timecode(end),
                    "start_frame": int(start * frame_rate),
                    "end_frame": int(end * frame_rate),
                    "duration": format_timecode(end - start)
                })

            return { "scenes": scenes, "total_scenes": len(scenes) }
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

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

    async def _detect_scenes(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> List[float]:
        command: List[str] = [ "ffmpeg", "-hide_banner" ]

        if start_time is not None:
            command.extend([ "-ss", str(start_time) ])
        if end_time is not None:
            command.extend([ "-to", str(end_time) ])

        command.extend([ "-i", input_path ])
        command.extend([ "-vf", f"select='gt(scene,{threshold})',showinfo" ])
        command.extend([ "-f", "null", "-" ])

        logging.debug(f"Detecting scenes with ffmpeg (threshold={threshold})")

        process, _, timestamps = await run_subprocess(
            command,
            stderr_handler=self._handle_stderr,
        )

        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg scene detection failed (exit code {process.returncode})")

        return timestamps

    async def _handle_stderr(self, reader: asyncio.StreamReader) -> List[float]:
        timestamps: List[float] = []

        while True:
            line = await reader.readline()
            if not line:
                break
            match = _PTS_TIME_PATTERN.search(line)
            if match:
                timestamps.append(float(match.group(1)))

        return timestamps

    async def _get_frame_rate(self, input_path: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-select_streams", "v:0", "-show_streams", input_path,
        ]

        stdout, _, returncode = await run_command(command)

        if returncode != 0:
            raise RuntimeError(f"ffprobe failed to read frame rate (exit code {returncode})")

        result = json.loads(stdout.decode("utf-8"))
        frame_rate = result["streams"][0].get("r_frame_rate", "30/1")
        numerator, denominator = frame_rate.split("/")

        return float(numerator) / float(denominator)

    async def _get_duration(self, input_path: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", input_path,
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

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoSceneDetectorAction(action).run(context)
