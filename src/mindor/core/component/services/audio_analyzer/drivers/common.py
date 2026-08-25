from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioAnalyzerActionConfig
from mindor.dsl.schema.action.impl.audio_analyzer.impl.common import AudioAnalyzerMetric
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

class AudioAnalyzerAction(ComponentAction):
    def __init__(self, config: AudioAnalyzerActionConfig):
        self.config: AudioAnalyzerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.metric, context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._analyze_batch(batch_audios, self.config.metric, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._analyze_batch(batch_audios, self.config.metric, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, metric: AudioAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        if metric == AudioAnalyzerMetric.LOUDNESS:
            target_loudness  = await context.render_scalar(self.config.target_loudness, float)
            include_timeline = await context.render_scalar(self.config.include_timeline, bool)

            return {
                "target_loudness":  target_loudness,
                "include_timeline": include_timeline,
            }

        if metric == AudioAnalyzerMetric.PEAK:
            true_peak = await context.render_scalar(self.config.true_peak, bool)

            return {
                "true_peak": true_peak,
            }

        if metric == AudioAnalyzerMetric.GAIN:
            return {}

        if metric == AudioAnalyzerMetric.CLIPPING:
            threshold               = await context.render_scalar(self.config.threshold, float)
            min_consecutive_length = await context.render_scalar(self.config.min_consecutive_length, int)

            return {
                "threshold":               threshold,
                "min_consecutive_length": min_consecutive_length,
            }

        if metric == AudioAnalyzerMetric.SILENCE:
            threshold    = await context.render_scalar(self.config.threshold, float)
            min_duration = await context.render_scalar(self.config.min_duration, "time")

            return {
                "threshold":    threshold,
                "min_duration": min_duration,
            }

        if metric == AudioAnalyzerMetric.ENERGY:
            threshold        = await context.render_scalar(self.config.threshold, float)
            segment_duration = await context.render_scalar(self.config.segment_duration, "time")
            resolution       = await context.render_scalar(self.config.resolution, "time")

            if resolution is None or resolution <= 0.0:
                raise ValueError(f"'resolution' must be > 0, got {resolution}")

            if segment_duration is not None and segment_duration <= 0.0:
                raise ValueError(f"'segment_duration' must be > 0 when provided, got {segment_duration}")

            return {
                "threshold":        threshold,
                "segment_duration": segment_duration,
                "resolution":       resolution,
            }

        raise ValueError(f"Unsupported audio metric: {metric}")

    async def _analyze_batch(
        self,
        audios: List[MediaSource],
        metric: AudioAnalyzerMetric,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._analyze(metric, audio, params, cancellation_token) for audio in audios
        ])

    async def _analyze(
        self,
        metric: AudioAnalyzerMetric,
        source: MediaSource,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == AudioAnalyzerMetric.LOUDNESS:
            return await self._analyze_loudness(source, params, cancellation_token)

        if metric == AudioAnalyzerMetric.PEAK:
            return await self._analyze_peak(source, params, cancellation_token)

        if metric == AudioAnalyzerMetric.GAIN:
            return await self._analyze_gain(source, params, cancellation_token)

        if metric == AudioAnalyzerMetric.CLIPPING:
            return await self._analyze_clipping(source, params, cancellation_token)

        if metric == AudioAnalyzerMetric.SILENCE:
            return await self._analyze_silence(source, params, cancellation_token)

        if metric == AudioAnalyzerMetric.ENERGY:
            return await self._analyze_energy(source, params, cancellation_token)

        raise ValueError(f"Unsupported audio metric: {metric}")

    @abstractmethod
    async def _analyze_loudness(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_peak(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_gain(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_clipping(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_silence(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_energy(self, source: MediaSource, params: Dict[str, Any], cancellation_token: Optional[CancellationToken] = None) -> Dict[str, Any]:
        pass
