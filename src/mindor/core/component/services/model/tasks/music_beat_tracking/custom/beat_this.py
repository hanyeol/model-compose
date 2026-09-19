from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Tuple, Any
from mindor.dsl.schema.component import ModelComponentConfig, BeatThisMusicBeatTrackingModelComponentConfig, ModelPrecision
from mindor.dsl.schema.action import ModelActionConfig, BeatThisMusicBeatTrackingModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.package.torch import torch_requirements
from mindor.core.utils.ffmpeg.probe import probe_audio
from ......base import ComponentActionContext
from ......action.media import MediaInputPathResolver
from ....base import ModelTaskDriver
from ..common import MusicBeatTrackingTaskAction, MusicBeats
import os

if TYPE_CHECKING:
    from beat_this.inference import File2Beats
    import numpy as np
    import torch

class BeatThisMusicBeatTrackingTaskAction(MusicBeatTrackingTaskAction):
    def __init__(
        self,
        config: BeatThisMusicBeatTrackingModelActionConfig,
        tracker: File2Beats,
        device: Optional[torch.device],
    ):
        super().__init__(config, device)

        self.config: BeatThisMusicBeatTrackingModelActionConfig = config
        self.tracker: File2Beats = tracker

    async def _track_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        audio_paths: List[str] = []
        spooled_paths: List[str] = []

        for audio in audios:
            path, spooled = await MediaInputPathResolver().resolve(audio)
            audio_paths.append(path)

            if spooled:
                spooled_paths.append(path)

        durations = [
            await self._probe_duration(path) if params["return_metadata"] else None
            for path in audio_paths
        ]

        def _track() -> List[Any]:
            return [
                self._build_tracking_result(*self.tracker(path), duration, params)
                for path, duration in zip(audio_paths, durations)
            ]

        try:
            return await self._run_in_executor(_track)
        finally:
            for path in spooled_paths:
                try:
                    os.remove(path)
                except OSError:
                    pass

    def _build_tracking_result(
        self,
        beat_times: np.ndarray,
        downbeat_times: np.ndarray,
        duration: Optional[float],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "beats": MusicBeats(self._build_beat_events(beat_times, downbeat_times)),
        }

        if params["return_metadata"] and duration is not None:
            result["duration"] = duration

        return result

    def _build_beat_events(self, beat_times: np.ndarray, downbeat_times: np.ndarray) -> List[Dict[str, Any]]:
        downbeat_set = { float(time) for time in downbeat_times }
        events: List[Dict[str, Any]] = []
        beat_number: Optional[int] = None

        for time in beat_times:
            time = float(time)
            is_downbeat = time in downbeat_set

            if is_downbeat:
                beat_number = 1
            elif beat_number is not None:
                beat_number += 1

            events.append({
                "time":        time,
                "is_downbeat": is_downbeat,
                "beat_number": beat_number,
            })

        return events

    async def _probe_duration(self, audio_path: str) -> Optional[float]:
        (duration,) = await probe_audio(audio_path, [ "duration" ])

        if duration is not None:
            return float(duration)

        return None

class BeatThisMusicBeatTrackingTaskDriver(ModelTaskDriver):
    config: BeatThisMusicBeatTrackingModelComponentConfig

    def __init__(self, id: str, config: BeatThisMusicBeatTrackingModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.tracker: Optional[File2Beats] = None
        self.device: Optional[torch.device] = None

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return [ *torch_requirements("torch", "torchaudio"), "beat_this" ]

    async def _load_model(self) -> None:
        self.tracker, self.device = await self._load_tracker()

    async def _unload_model(self) -> None:
        self.tracker = None
        self.device = None

    async def _load_tracker(self) -> Tuple[File2Beats, torch.device]:
        from beat_this.inference import File2Beats

        device = self._resolve_device(self.config.device)

        # beat_this only exposes a boolean float16 knob; map the generic
        # precision enum onto it (bfloat16 falls back to fp32 because the model
        # doesn't support it).
        float16 = self.config.precision == ModelPrecision.FLOAT16

        def _load() -> File2Beats:
            return File2Beats(
                checkpoint_path=self.config.model.name,
                device=str(device),
                float16=float16,
                dbn=bool(self.config.dbn),
            )

        tracker = await self._run_in_executor(_load)

        return tracker, device

    async def _run(self, action: ModelActionConfig, context: ComponentActionContext) -> Any:
        return await BeatThisMusicBeatTrackingTaskAction(action, self.tracker, self.device).run(context)
