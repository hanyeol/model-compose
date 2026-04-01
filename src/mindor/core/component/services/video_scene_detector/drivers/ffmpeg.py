from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.logger import logging
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext
import asyncio
import json
import re

class FFmpegVideoSceneDetectorAction:
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_file(self.config.video)
        threshold  = await context.render_variable(self.config.threshold) if self.config.threshold else 0.3
        start_time = await context.render_variable(self.config.start_time) if self.config.start_time else None
        end_time   = await context.render_variable(self.config.end_time) if self.config.end_time else None

        scenes = await self._detect(video, float(threshold), start_time, end_time)

        context.register_source("result", scenes)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else scenes

    async def _detect(
        self,
        video: str,
        threshold: float,
        start_time: Optional[str],
        end_time: Optional[str]
    ) -> Dict[str, Any]:
        timestamps = await self._detect_scenes(video, threshold, start_time, end_time)
        duration   = await self._get_duration(video)
        frame_rate = await self._get_frame_rate(video)

        scenes: List[Dict[str, Any]] = []
        boundaries = [ 0.0 ] + timestamps + [ duration ]

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            scenes.append({
                "index": i,
                "start": self._format_timecode(start),
                "end": self._format_timecode(end),
                "start_frame": int(start * frame_rate),
                "end_frame": int(end * frame_rate),
                "duration": self._format_timecode(end - start)
            })

        return { "scenes": scenes, "total_scenes": len(scenes) }

    async def _detect_scenes(
        self,
        video: str,
        threshold: float,
        start_time: Optional[str],
        end_time: Optional[str]
    ) -> List[float]:
        command = [
            "ffmpeg", "-hide_banner", "-i", video,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-"
        ]

        if start_time:
            command = [
                "ffmpeg", "-hide_banner", "-ss", start_time, "-i", video,
                "-vf", f"select='gt(scene,{threshold})',showinfo",
                "-f", "null", "-"
            ]

            if end_time:
                command.insert(command.index("-i"), "-to")
                command.insert(command.index("-i"), end_time)

        logging.info(f"Detecting scenes in '{video}' with ffmpeg (threshold={threshold})")

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        _, stderr = await process.communicate()
        output = stderr.decode("utf-8", errors="replace")

        timestamps: List[float] = []
        for match in re.finditer(r"pts_time:(\d+\.?\d*)", output):
            timestamps.append(float(match.group(1)))

        return timestamps

    async def _get_frame_rate(self, video: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-select_streams", "v:0", "-show_streams", video
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _ = await process.communicate()
        result = json.loads(stdout.decode("utf-8"))

        frame_rate = result["streams"][0].get("r_frame_rate", "30/1")
        numerator, denominator = frame_rate.split("/")

        return float(numerator) / float(denominator)

    async def _get_duration(self, video: str) -> float:
        command = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", video
        ]

        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, _ = await process.communicate()
        result = json.loads(stdout.decode("utf-8"))

        return float(result["format"]["duration"])

    @staticmethod
    def _format_timecode(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}"

@register_video_scene_detector_service(VideoSceneDetectorDriver.FFMPEG)
class FFmpegVideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await FFmpegVideoSceneDetectorAction(action).run(context)
