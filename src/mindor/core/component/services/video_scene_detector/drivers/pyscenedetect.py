from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig, VideoSceneDetectorType
from mindor.core.logger import logging
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext

class PySceneVideoSceneDetectorAction:
    def __init__(self, config: VideoSceneDetectorActionConfig):
        self.config: VideoSceneDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        video      = await context.render_file(self.config.video)
        detector   = await context.render_variable(self.config.detector) if self.config.detector else None
        threshold  = await context.render_variable(self.config.threshold) if self.config.threshold else None
        start_time = await context.render_variable(self.config.start_time) if self.config.start_time else None
        end_time   = await context.render_variable(self.config.end_time) if self.config.end_time else None

        scenes = self._detect(video, detector, threshold, start_time, end_time)

        result = {
            "scenes": [
                {
                    "index": i,
                    "start": start.get_timecode(),
                    "end": end.get_timecode(),
                    "start_frame": start.get_frames(),
                    "end_frame": end.get_frames(),
                    "duration": (end - start).get_timecode()
                }
                for i, (start, end) in enumerate(scenes)
            ],
            "total_scenes": len(scenes)
        }

        context.register_source("result", result)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    def _detect(self, video: str, detector: Optional[str], threshold: Optional[float], start_time: Optional[str], end_time: Optional[str]) -> List:
        from scenedetect import detect

        scene_detector = self._create_detector(detector, threshold)

        kwargs: Dict[str, Any] = {}
        if start_time:
            kwargs["start_time"] = start_time
        if end_time:
            kwargs["end_time"] = end_time

        logging.info(f"Detecting scenes in '{video}' with {type(scene_detector).__name__}")

        return detect(video, scene_detector, **kwargs)

    def _create_detector(self, detector: Optional[str], threshold: Optional[float]) -> Any:
        detector = detector or VideoSceneDetectorType.ADAPTIVE

        if detector == VideoSceneDetectorType.CONTENT:
            from scenedetect import ContentDetector
            return ContentDetector(threshold=threshold) if threshold is not None else ContentDetector()

        if detector == VideoSceneDetectorType.ADAPTIVE:
            from scenedetect import AdaptiveDetector
            return AdaptiveDetector(adaptive_threshold=threshold) if threshold is not None else AdaptiveDetector()

        if detector == VideoSceneDetectorType.THRESHOLD:
            from scenedetect import ThresholdDetector
            return ThresholdDetector(threshold=threshold) if threshold is not None else ThresholdDetector()

        if detector == VideoSceneDetectorType.HISTOGRAM:
            from scenedetect import HistogramDetector
            return HistogramDetector(threshold=threshold) if threshold is not None else HistogramDetector()

        if detector == VideoSceneDetectorType.HASH:
            from scenedetect import HashDetector
            return HashDetector(threshold=threshold) if threshold is not None else HashDetector()

        raise ValueError(f"Unsupported detector type: {detector}")

@register_video_scene_detector_service(VideoSceneDetectorDriver.PYSCENEDETECT)
class PySceneVideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "scenedetect[opencv]" ]

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await PySceneVideoSceneDetectorAction(action).run(context)
