from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Tuple, Union, Callable, Any
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, TransNetV2ShotBoundaryDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.component.action.media import MediaInputPathResolver
from mindor.core.utils.ffmpeg.probe import probe_video
from mindor.core.utils.time import format_timecode
from mindor.core.logger import logging
from ..common import ShotBoundaryDetectionTaskAction
from ....base import ComponentActionContext, ModelTaskService
import os

if TYPE_CHECKING:
    from transnetv2 import TransNetV2
    import numpy as np

class TransNetV2ShotBoundaryDetectionTaskAction(ShotBoundaryDetectionTaskAction):
    def __init__(self, config: TransNetV2ShotBoundaryDetectionModelActionConfig, model: TransNetV2):
        super().__init__(config)

        self.model: TransNetV2 = model

    async def _detect_batch(
        self,
        videos: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]] = []

        for video in videos:
            results.append(await self._detect(
                video,
                params["threshold"],
                params["start_time"],
                params["end_time"],
                streaming,
                cancellation_token,
            ))

        return results

    async def _detect(
        self,
        video: MediaSource,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]:
        input_path, spooled = await MediaInputPathResolver().resolve(video)

        def _cleanup() -> None:
            if spooled:
                try:
                    os.remove(input_path)
                except FileNotFoundError:
                    pass

        if streaming:
            return self._stream_shots(input_path, threshold, start_time, end_time, _cleanup, cancellation_token)

        return await self._collect_shots(input_path, threshold, start_time, end_time, _cleanup, cancellation_token)

    async def _collect_shots(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        try:
            shots = await self._detect_shots(input_path, threshold, start_time, end_time)

            logging.debug(f"TransNetV2 detected {len(shots)} shots")

            return shots
        finally:
            cleanup()

    async def _stream_shots(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
        cleanup: Callable[[], None],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        try:
            shots = await self._detect_shots(input_path, threshold, start_time, end_time)

            for shot in shots:
                yield shot
        finally:
            cleanup()

    async def _detect_shots(
        self,
        input_path: str,
        threshold: float,
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> List[Dict[str, Any]]:
        frame_rate, = await probe_video(input_path, ("frame_rate",))

        def _detect() -> List[Dict[str, Any]]:
            _, predictions, _ = self.model.predict_video(input_path)

            offset = int(start_time * frame_rate) if start_time is not None else 0
            end_frame = int(end_time * frame_rate) if end_time is not None else len(predictions)
            window = predictions[offset:end_frame]

            if len(window) == 0:
                return []

            scenes = self._predictions_to_scenes(window, threshold)
            results: List[Dict[str, Any]] = []

            for index, (start_frame, end_frame) in enumerate(scenes):
                absolute_start = start_frame + offset
                absolute_end = end_frame + offset
                start_seconds = absolute_start / frame_rate
                end_seconds = absolute_end / frame_rate

                results.append({
                    "index": index,
                    "start_time": format_timecode(start_seconds),
                    "end_time": format_timecode(end_seconds),
                    "start_frame": int(absolute_start),
                    "end_frame": int(absolute_end),
                    "duration": format_timecode(end_seconds - start_seconds),
                })

            return results

        return await self._run_in_executor(_detect)

    @staticmethod
    def _predictions_to_scenes(predictions: np.ndarray, threshold: float) -> List[Tuple[int, int]]:
        # Follows the reference `TransNetV2.predictions_to_scenes` implementation:
        # emit (start, end) frame pairs on falling/rising edges of the binarized
        # per-frame boundary prediction. Consecutive boundary frames stay merged
        # into one shot rather than producing many one-frame segments.
        import numpy as np

        binary = (predictions > threshold).astype(np.uint8)

        scenes: List[Tuple[int, int]] = []
        prev, start, current = 0, 0, -1

        for index, current in enumerate(binary):
            if prev == 1 and current == 0:
                start = index
            if prev == 0 and current == 1 and index != 0:
                scenes.append((start, index))
            prev = current

        if current == 0:
            scenes.append((start, len(binary) - 1))

        if not scenes:
            return [(0, len(binary) - 1)]

        return scenes

class TransNetV2ShotBoundaryDetectionTaskService(ModelTaskService):
    def __init__(self, id: str, config: ModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[TransNetV2] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [
            "transnetv2@git+https://github.com/soCzech/TransNetV2.git",
            "ffmpeg-python",
            "tensorflow",
        ]

    async def _load_model(self) -> None:
        from transnetv2 import TransNetV2

        model_dir = await self._provision_model(self.config.model, prefetch=True)
        self.model = TransNetV2(model_dir=model_dir)

    async def _unload_model(self) -> None:
        self.model = None

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await TransNetV2ShotBoundaryDetectionTaskAction(action, self.model).run(context)
