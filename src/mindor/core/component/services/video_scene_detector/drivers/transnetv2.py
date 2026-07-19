from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Union, Callable, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig
from mindor.dsl.schema.action import VideoSceneDetectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.streaming.resources import save_stream_to_temporary_file
from mindor.core.foundation.streaming.file import FileStreamResource
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
        end_time: Optional[float],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]:
        input_path, spooled = await self._resolve_input_path(video)
        threshold = threshold if threshold is not None else 0.5

        def _cleanup() -> None:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        if streaming:
            return self._stream_scenes(input_path, threshold, start_time, end_time, _cleanup, cancellation_token)

        return await self._collect_scenes(input_path, threshold, start_time, end_time, _cleanup, cancellation_token)

    async def _collect_scenes(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        try:
            scene_frames, frame_rate = await self._detect_scenes(input_path, threshold, start_time, end_time)

            scenes: List[Dict[str, Any]] = []

            for index in range(len(scene_frames) - 1):
                start_frame = scene_frames[index]
                end_frame = scene_frames[index + 1]
                start = start_frame / frame_rate
                end = end_frame / frame_rate

                scenes.append({
                    "index": index,
                    "start": format_timecode(start),
                    "end": format_timecode(end),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "duration": format_timecode(end - start)
                })

            logging.debug(f"TransNetV2 detected {len(scenes)} scenes")

            return scenes
        finally:
            cleanup()

    async def _stream_scenes(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        try:
            scene_frames, frame_rate = await self._detect_scenes(input_path, threshold, start_time, end_time)

            for index in range(len(scene_frames) - 1):
                start_frame = scene_frames[index]
                end_frame = scene_frames[index + 1]
                start = start_frame / frame_rate
                end = end_frame / frame_rate

                yield {
                    "index": index,
                    "start": format_timecode(start),
                    "end": format_timecode(end),
                    "start_frame": start_frame,
                    "end_frame": end_frame,
                    "duration": format_timecode(end - start),
                }
        finally:
            cleanup()

    async def _detect_scenes(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> Tuple[List[int], float]:
        import numpy as np

        predictions = self._predict(input_path)
        frame_rate  = await self._get_frame_rate(input_path)

        start_frame = int(start_time * frame_rate) if start_time is not None else 0
        end_frame   = int(end_time * frame_rate) if end_time is not None else len(predictions)
        predictions = predictions[start_frame:end_frame]

        total_frames = len(predictions)

        if total_frames == 0:
            return [], frame_rate

        boundaries = np.where(predictions > threshold)[0]

        return [0] + boundaries.tolist() + [ total_frames ], frame_rate

    def _predict(self, video: str) -> Any:
        from transnetv2 import TransNetV2

        model = TransNetV2()
        _, predictions, _ = model.predict_video(video)

        return predictions

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

@register_video_scene_detector_service(VideoSceneDetectorDriver.TRANSNETV2)
class TransNetV2VideoSceneDetectorService(VideoSceneDetectorService):
    def __init__(self, id: str, config: VideoSceneDetectorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "transnetv2" ]

    async def _run(self, action: VideoSceneDetectorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await TransNetV2VideoSceneDetectorAction(action).run(context, loop)
