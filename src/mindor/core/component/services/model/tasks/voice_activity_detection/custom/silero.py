from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, SileroVoiceActivityDetectionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, VoiceActivityDetectionModelActionConfig
from mindor.core.foundation.streaming.audio import load_audio_array
from mindor.core.foundation.streaming.media import MediaSource
from ......base import ComponentActionContext
from ..common import VoiceActivityDetectionTaskService, VoiceActivityDetectionTaskAction
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

WINDOW_SIZE_SAMPLES_16K = 512
WINDOW_SIZE_SAMPLES_8K  = 256

class SileroVoiceActivityDetectionTaskAction(VoiceActivityDetectionTaskAction):
    def __init__(
        self,
        config: VoiceActivityDetectionModelActionConfig,
        model: Any,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: Any = model

    async def _detect(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        target_sr = int(params["sample_rate"])
        waveforms = [ await self._preprocess_audio(audio, target_sr) for audio in audios ]

        if streaming:
            return [ self._detect_stream(waveform, target_sr, params) for waveform in waveforms ]

        return [ self._detect_full(waveform, target_sr, params) for waveform in waveforms ]

    def _detect_full(self, waveform: np.ndarray, sample_rate: int, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        import torch
        from silero_vad import get_speech_timestamps

        tensor = torch.from_numpy(waveform)
        timestamps = get_speech_timestamps(
            tensor,
            self.model,
            sampling_rate=sample_rate,
            threshold=float(params["threshold"]),
            min_speech_duration_ms=int(params["min_speech_duration"] * 1000),
            min_silence_duration_ms=int(params["min_silence_duration"] * 1000),
            speech_pad_ms=int(params["speech_padding_time"] * 1000),
            return_seconds=False,
        )

        return [ self._build_segment(tensor, ts, sample_rate) for ts in timestamps ]

    def _detect_stream(self, waveform: np.ndarray, sample_rate: int, params: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        import torch
        from silero_vad import get_speech_timestamps

        tensor = torch.from_numpy(waveform)
        timestamps = get_speech_timestamps(
            tensor,
            self.model,
            sampling_rate=sample_rate,
            threshold=float(params["threshold"]),
            min_speech_duration_ms=int(params["min_speech_duration"] * 1000),
            min_silence_duration_ms=int(params["min_silence_duration"] * 1000),
            speech_pad_ms=int(params["speech_padding_time"] * 1000),
            return_seconds=False,
        )

        for ts in timestamps:
            yield self._build_segment(tensor, ts, sample_rate)

    async def _preprocess_audio(self, audio: MediaSource, target_sample_rate: int) -> np.ndarray:
        import numpy as np
        import torch
        import torchaudio.functional as F

        waveform, sample_rate = await load_audio_array(audio)

        if waveform.ndim > 1:
            waveform = waveform.mean(axis=0)

        if sample_rate != target_sample_rate:
            tensor = torch.from_numpy(waveform).float()
            waveform = F.resample(tensor, sample_rate, target_sample_rate).numpy()

        return waveform.astype(np.float32)

    def _build_segment(self, waveform: torch.Tensor, timestamp: Dict[str, int], sample_rate: int) -> Dict[str, Any]:
        start_sample = int(timestamp["start"])
        end_sample = int(timestamp["end"])

        return {
            "start":      start_sample / sample_rate,
            "end":        end_sample / sample_rate,
            "confidence": self._compute_confidence(waveform, start_sample, end_sample, sample_rate),
        }

    def _compute_confidence(self, waveform: torch.Tensor, start_sample: int, end_sample: int, sample_rate: int) -> float:
        import torch

        window_size = WINDOW_SIZE_SAMPLES_16K if sample_rate == 16000 else WINDOW_SIZE_SAMPLES_8K

        start_sample = max(0, start_sample)
        end_sample = min(int(waveform.shape[-1]), end_sample)

        if end_sample <= start_sample:
            return 0.0

        probs: List[float] = []
        self.model.reset_states()

        with torch.no_grad():
            for offset in range(start_sample, end_sample, window_size):
                chunk = waveform[offset:offset + window_size]
                if chunk.shape[-1] < window_size:
                    chunk = torch.nn.functional.pad(chunk, (0, window_size - chunk.shape[-1]))
                prob = self.model(chunk, sample_rate).item()
                probs.append(prob)

        self.model.reset_states()

        return float(sum(probs) / len(probs)) if probs else 0.0

class SileroVoiceActivityDetectionTaskService(VoiceActivityDetectionTaskService):
    config: SileroVoiceActivityDetectionModelComponentConfig

    def __init__(self, id: str, config: SileroVoiceActivityDetectionModelComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.model: Optional[Any] = None
        self.device: Optional[torch.device] = None

    def get_setup_requirements(self) -> Optional[List[str]]:
        return [ "silero-vad", "torch", "torchaudio", "numpy" ]

    async def _load_model(self) -> None:
        self.model, self.device = self._load_pretrained_model()

    async def _unload_model(self) -> None:
        self.model = None
        self.device = None

    def _load_pretrained_model(self) -> Tuple[Any, torch.device]:
        from silero_vad import load_silero_vad

        device = self._resolve_device(self.config.device)
        model = load_silero_vad()

        return model, device

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop,
    ) -> Any:
        return await SileroVoiceActivityDetectionTaskAction(action, self.model, self.device).run(context, loop)
