from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Dict, Optional, List, Iterator, Tuple, Union, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ModelComponentConfig, SileroVoiceActivityDetectionModelComponentConfig
from mindor.dsl.schema.action import ModelActionConfig, VoiceActivityDetectionModelActionConfig
from mindor.core.foundation.streaming.audio import load_audio_array, stream_audio_array, is_audio_streamable
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.logger import logging
from ......base import ComponentActionContext
from ..common import VoiceActivityDetectionTaskService, VoiceActivityDetectionTaskAction, VoiceSegmenter
import asyncio

if TYPE_CHECKING:
    import numpy as np
    import torch

_WINDOW_SIZE_SAMPLES_16K = 512
_WINDOW_SIZE_SAMPLES_8K  = 256

class SileroVoiceActivityDetectionTaskAction(VoiceActivityDetectionTaskAction):
    def __init__(
        self,
        config: VoiceActivityDetectionModelActionConfig,
        model: Any,
        device: Optional[torch.device]
    ):
        super().__init__(config, device)

        self.model: Any = model

    async def _detect(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop
    ) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        import numpy as np

        sample_rate = int(params["sample_rate"])
        sources, window_size = await self._preprocess_audio(audios, sample_rate, streaming)
        results = []

        for source in sources:
            if isinstance(source, np.ndarray):
                segments = self._collect_detections(source, sample_rate, params)
                if streaming:
                    # Streaming requested but source not consumable frame-by-frame:
                    # yield the batch segments one by one to preserve the
                    # AsyncIterator interface expected by downstream jobs.
                    async def _stream_chunk_generator(segments=segments):
                        for segment in segments:
                            yield segment
                    results.append(_stream_chunk_generator())
                else:
                    results.append(segments)
            else:
                results.append(self._stream_detections(source, window_size, sample_rate, params))

        return results

    async def _preprocess_audio(
        self,
        audios: List[MediaSource],
        sample_rate: int,
        streaming: bool,
    ) -> Tuple[List[Union[np.ndarray, AsyncIterator[np.ndarray]]], int]:
        import numpy as np

        window_size = self._resolve_window_size(sample_rate)
        waveforms: List[Union[np.ndarray, AsyncIterator[np.ndarray]]] = []

        for audio in audios:
            if streaming and is_audio_streamable(audio):
                waveforms.append(stream_audio_array(audio, window_size, sample_rate=sample_rate))
                continue

            if streaming:
                logging.debug("Streaming input format=%r not directly consumable; collating for frame-by-frame VAD.", audio.format)

            waveform, _ = await load_audio_array(audio, sample_rate=sample_rate)
            waveforms.append(waveform)

        return waveforms, window_size

    def _collect_detections(
        self,
        waveform: np.ndarray,
        sample_rate: int,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        from silero_vad import get_speech_timestamps
        import torch

        tensor = torch.from_numpy(waveform)
        timestamps = get_speech_timestamps(
            tensor,
            self.model,
            sampling_rate=sample_rate,
            threshold=float(params["threshold"]),
            min_speech_duration_ms=int(params["min_speech_duration"] * 1000),
            max_speech_duration_s=params["max_speech_duration"] if params["max_speech_duration"] is not None else float("inf"),
            min_silence_duration_ms=int(params["min_silence_duration"] * 1000),
            speech_pad_ms=int(params["speech_padding_time"] * 1000),
            return_seconds=False,
        )

        return [ self._build_segment(tensor, timestamp, sample_rate) for timestamp in timestamps ]

    async def _stream_detections(
        self,
        frames: AsyncIterator[np.ndarray],
        window_size: int,
        sample_rate: int,
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        import torch

        segmenter = self._create_segmenter(sample_rate, params)
        offset = 0  # samples consumed so far

        self.model.reset_states()
        try:
            with torch.no_grad():
                async for frame in frames:
                    tensor = torch.from_numpy(frame)
                    prob = self.model(tensor, sample_rate).item()

                    segment = segmenter.feed(prob, offset)
                    if segment is not None:
                        # audio_length is not known ahead of time; clamp trailing padding to current offset + pad.
                        yield self._build_padded_segment(
                            *segment,
                            offset + segmenter.speech_pad_samples,
                            sample_rate,
                            segmenter.speech_pad_samples,
                        )

                    offset += window_size

            trailing = segmenter.flush(offset)
            if trailing is not None:
                yield self._build_padded_segment(
                    *trailing,
                    offset,
                    sample_rate,
                    segmenter.speech_pad_samples,
                )
        finally:
            self.model.reset_states()

    def _resolve_window_size(self, sample_rate: int) -> int:
        if sample_rate == 16000:
            return _WINDOW_SIZE_SAMPLES_16K

        if sample_rate == 8000:
            return _WINDOW_SIZE_SAMPLES_8K

        raise ValueError(f"Silero VAD supports only 8000 or 16000 Hz; got sample_rate={sample_rate}")

    def _create_segmenter(self, sample_rate: int, params: Dict[str, Any]) -> VoiceSegmenter:
        threshold = float(params["threshold"])

        return VoiceSegmenter(
            threshold=threshold,
            neg_threshold=max(threshold - 0.15, 0.01),
            min_speech_samples=int(params["min_speech_duration"] * sample_rate),
            min_silence_samples=int(params["min_silence_duration"] * sample_rate),
            speech_pad_samples=int(params["speech_padding_time"] * sample_rate),
        )

    def _build_segment(self, waveform: torch.Tensor, timestamp: Dict[str, int], sample_rate: int) -> Dict[str, Any]:
        start_sample = int(timestamp["start"])
        end_sample = int(timestamp["end"])

        return {
            "start":      start_sample / sample_rate,
            "end":        end_sample / sample_rate,
            "confidence": self._compute_confidence(waveform, start_sample, end_sample, sample_rate),
        }

    def _build_padded_segment(
        self,
        start_sample: int,
        end_sample: int,
        probs: List[float],
        audio_length: int,
        sample_rate: int,
        pad_samples: int,
    ) -> Dict[str, Any]:
        padded_start = max(0, start_sample - pad_samples)
        padded_end   = min(audio_length, end_sample + pad_samples)

        return {
            "start":      padded_start / sample_rate,
            "end":        padded_end / sample_rate,
            "confidence": float(sum(probs) / len(probs)) if probs else 0.0,
        }

    def _compute_confidence(self, waveform: torch.Tensor, start_sample: int, end_sample: int, sample_rate: int) -> float:
        import torch

        window_size = self._resolve_window_size(sample_rate)

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
        return [ "silero-vad", "torch", "torchaudio", "numpy", "soxr" ]

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
