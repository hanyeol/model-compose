from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig, VideoSceneDetectorType
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.logger import logging
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext
from .common import VideoSceneDetectorAction
import asyncio, os

class PySceneVideoSceneDetectorAction(VideoSceneDetectorAction):
    async def _detect(
        self,
        video: MediaSource,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> Dict[str, Any]:
        input_path, spooled = await self._resolve_input_path(video)

        try:
            scenes = await asyncio.to_thread(self._detect_scenes, input_path, detector, threshold, start_time, end_time)

            return {
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
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    async def _resolve_input_path(self, video: MediaSource) -> Tuple[str, bool]:
        """
        PySceneDetect requires an on-disk path.

        - FileStreamResource: use its path directly (no spooling).
        - Otherwise: spool the stream to a temp file.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(video.stream, FileStreamResource):
            return video.stream.path, False

        logging.debug("Spooling video stream to a temp file before scene detection")

        spooled_path = await save_stream_to_temporary_file(video.stream, video.format)

        return spooled_path, True

    def _detect_scenes(
        self,
        video: str,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> List:
        from scenedetect import detect

        scene_detector = self._create_detector(detector, threshold)

        params: Dict[str, Any] = {}
        if start_time:
            params["start_time"] = start_time
        if end_time:
            params["end_time"] = end_time

        logging.debug(f"Detecting scenes in '{video}' with {type(scene_detector).__name__}")

        return detect(video, scene_detector, **params)

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
