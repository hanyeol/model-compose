from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Union, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig, VideoSceneDetectorType
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
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
        end_time: Optional[float],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        input_path, spooled = await self._resolve_input_path(video)

        def _cleanup() -> None:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        if streaming:
            return self._stream_scenes(input_path, detector, threshold, start_time, end_time, _cleanup)

        return await self._collect_scenes(input_path, detector, threshold, start_time, end_time, _cleanup)

    async def _collect_scenes(
        self,
        input_path: str,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
    ) -> List[Dict[str, Any]]:
        try:
            scenes = self._detect_scenes(input_path, detector, threshold, start_time, end_time)
            results: List[Dict[str, Any]] = []

            for index, (start, end) in enumerate(scenes):
                results.append({
                    "index": index,
                    "start": start.get_timecode(),
                    "end": end.get_timecode(),
                    "start_frame": start.get_frames(),
                    "end_frame": end.get_frames(),
                    "duration": (end - start).get_timecode()
                })

            return results
        finally:
            cleanup()

    async def _stream_scenes(
        self,
        input_path: str,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
    ) -> AsyncIterator[Dict[str, Any]]:
        try:
            scenes = self._detect_scenes(input_path, detector, threshold, start_time, end_time)

            for index, (start, end) in enumerate(scenes):
                yield {
                    "index": index,
                    "start": start.get_timecode(),
                    "end": end.get_timecode(),
                    "start_frame": start.get_frames(),
                    "end_frame": end.get_frames(),
                    "duration": (end - start).get_timecode(),
                }
        finally:
            cleanup()

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

@register_video_scene_detector_service(VideoSceneDetectorDriver.PYSCENEDETECT)
class PySceneVideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "scenedetect[opencv]" ]

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await PySceneVideoSceneDetectorAction(action).run(context, loop)
