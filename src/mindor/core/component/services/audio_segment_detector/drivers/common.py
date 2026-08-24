from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioSegmentDetectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

if TYPE_CHECKING:
    import numpy as np

class AudioSegmentDetectorAction(ComponentAction):
    def __init__(self, config: AudioSegmentDetectorActionConfig):
        self.config: AudioSegmentDetectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._detect_batch(batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._detect_batch(batch_audios, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        strategy             = await context.render_variable(self.config.strategy)
        return_labels        = await context.render_scalar(self.config.return_labels, bool)
        min_segment_duration = await context.render_scalar(self.config.min_segment_duration, "time")
        sample_rate          = await context.render_scalar(self.config.sample_rate, int)

        return {
            "strategy":             strategy,
            "return_labels":        return_labels,
            "min_segment_duration": min_segment_duration,
            "sample_rate":          sample_rate,
        }

    async def _detect_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for audio in audios:
            results.append(await self._detect(audio, params, cancellation_token))

        return results

    async def _detect(
        self,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        samples = await self._load_pcm_samples(source, params["sample_rate"])

        return await self._run_in_executor(self._segment, samples, params)

    def _segment(self, samples: np.ndarray, params: Dict[str, Any]) -> Dict[str, Any]:
        segments = self._detect_segments(samples, params)
        segments = self._enforce_min_duration(segments, params["min_segment_duration"])

        sample_rate = params["sample_rate"]
        duration = len(samples) / sample_rate if sample_rate else 0.0

        return {
            "segments": segments,
            "duration": duration,
            "sample_rate": sample_rate,
        }

    @staticmethod
    def _enforce_min_duration(segments: List[Dict[str, Any]], min_duration: Optional[float]) -> List[Dict[str, Any]]:
        if not min_duration or len(segments) <= 1:
            return segments

        merged: List[Dict[str, Any]] = []
        for segment in segments:
            if merged and (segment["end_time"] - segment["start_time"]) < min_duration:
                merged[-1]["end_time"] = segment["end_time"]
                continue
            merged.append(dict(segment))

        # tail sweep: if the final segment is too short, fold it into the previous one
        if len(merged) > 1 and (merged[-1]["end_time"] - merged[-1]["start_time"]) < min_duration:
            tail = merged.pop()
            merged[-1]["end_time"] = tail["end_time"]

        return merged

    @abstractmethod
    def _detect_segments(self, samples: np.ndarray, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return segments as [{start_time, end_time, label, confidence?}, ...] ordered by time."""
        pass

    @abstractmethod
    async def _load_pcm_samples(self, source: MediaSource, sample_rate: int) -> np.ndarray:
        """Load a media source as mono float32 samples in [-1, 1]."""
        pass
