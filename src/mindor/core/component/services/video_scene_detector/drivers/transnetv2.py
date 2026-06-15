from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streaming import FileStreamResource, save_stream_to_temporary_file
from mindor.core.utils.shell import run_command
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..base import VideoSceneDetectorService, VideoSceneDetectorDriver, register_video_scene_detector_service
from ..base import ComponentActionContext
from .common import VideoSceneDetectorAction
import asyncio, json, os

class TransNetV2VideoSceneDetectorAction(VideoSceneDetectorAction):
    async def _detect(
        self,
        video: MediaSource,
        detector: Optional[str],
        threshold: Optional[float],
        start_time: Optional[float],
        end_time: Optional[float]
    ) -> Dict[str, Any]:
        threshold = threshold if threshold is not None else 0.5
        input_path, spooled = await self._resolve_input_path(video)

        try:
            predictions = await asyncio.to_thread(self._predict, input_path)
            frame_rate  = await self._get_frame_rate(input_path)

            start_frame = int(start_time * frame_rate) if start_time is not None else 0
            end_frame   = int(end_time * frame_rate) if end_time is not None else len(predictions)
            predictions = predictions[start_frame:end_frame]

            return self._predictions_to_scenes(input_path, predictions, threshold, frame_rate)
        finally:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

    async def _resolve_input_path(self, video: MediaSource) -> Tuple[str, bool]:
        """
        TransNetV2 requires an on-disk path.

        - FileStreamResource: use its path directly (no spooling).
        - Otherwise: spool the stream to a temp file.

        Returns (input_path, spooled) — spooled=True means the caller owns the temp file cleanup.
        """
        if isinstance(video.stream, FileStreamResource):
            return video.stream.path, False

        logging.debug("Spooling video stream to a temp file before scene detection")

        spooled_path = await save_stream_to_temporary_file(video.stream, video.format)

        return spooled_path, True

    @staticmethod
    def _predict(video: str) -> Any:
        from transnetv2 import TransNetV2

        model = TransNetV2()
        _, predictions, _ = model.predict_video(video)

        return predictions

    @staticmethod
    def _predictions_to_scenes(video: str, predictions: Any, threshold: float, frame_rate: float) -> Dict[str, Any]:
        import numpy as np

        total_frames = len(predictions)

        if total_frames == 0:
            return { "scenes": [], "total_scenes": 0 }

        scene_boundaries = np.where(predictions > threshold)[0]

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

        logging.debug(f"TransNetV2 detected {len(scenes)} scenes in '{video}'")

        return { "scenes": scenes, "total_scenes": len(scenes) }

    @staticmethod
    async def _get_frame_rate(input_path: str) -> float:
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

@register_video_scene_detector_service(VideoSceneDetectorDriver.TRANSNETV2)
class TransNetV2VideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transnetv2" ]

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await TransNetV2VideoSceneDetectorAction(action).run(context)
