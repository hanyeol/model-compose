from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.logger import logging
from mindor.core.utils.time import format_timecode
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext
import asyncio
import json

class TransNetV2VideoSceneDetectorAction:
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video     = await context.render_file(self.config.video)
        threshold = await context.render_variable(self.config.threshold) if self.config.threshold else 0.5

        predictions = self._predict(video)
        frame_rate  = await self._get_frame_rate(video)

        result = self._build_result(video, predictions, float(threshold), frame_rate)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else result

    @staticmethod
    def _predict(video: str) -> Any:
        from transnetv2 import TransNetV2

        model = TransNetV2()
        _, single_frame_predictions, _ = model.predict_video(video)

        return single_frame_predictions

    @staticmethod
    def _build_result(video: str, single_frame_predictions: Any, threshold: float, frame_rate: float) -> Dict[str, Any]:
        import numpy as np

        scene_boundaries = np.where(single_frame_predictions > threshold)[0]
        total_frames = len(single_frame_predictions)

        scenes: List[Dict[str, Any]] = []
        boundaries = [0] + scene_boundaries.tolist() + [total_frames]

        for i in range(len(boundaries) - 1):
            start_frame = boundaries[i]
            end_frame = boundaries[i + 1]
            start_time = start_frame / frame_rate
            end_time = end_frame / frame_rate

            scenes.append({
                "index": i,
                "start": format_timecode(start_time),
                "end": format_timecode(end_time),
                "start_frame": start_frame,
                "end_frame": end_frame,
                "duration": format_timecode(end_time - start_time)
            })

        logging.info(f"TransNetV2 detected {len(scenes)} scenes in '{video}'")

        return { "scenes": scenes, "total_scenes": len(scenes) }

    @staticmethod
    async def _get_frame_rate(video: str) -> float:
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

@register_video_scene_detector_service(VideoSceneDetectorDriver.TRANSNETV2)
class TransNetV2VideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transnetv2" ]

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await TransNetV2VideoSceneDetectorAction(action).run(context)
