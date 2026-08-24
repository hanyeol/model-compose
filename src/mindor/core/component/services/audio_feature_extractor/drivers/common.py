from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.dsl.schema.action.impl.audio_feature_extractor.impl.common import AudioFeature
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class AudioSpectrum(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<AudioSpectrum bands={self.get('band_count')} "
            f"frames={self.get('frame_count')} "
            f"duration={self.get('duration', 0.0):.2f}s>"
        )

class AudioWaveform(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<AudioWaveform points={self.get('point_count')} "
            f"frames={self.get('frame_count')} "
            f"duration={self.get('duration', 0.0):.2f}s>"
        )

class AudioFeatureExtractorAction(ComponentAction):
    def __init__(self, config: AudioFeatureExtractorActionConfig):
        self.config: AudioFeatureExtractorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.feature, context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._extract_batch(batch_audios, self.config.feature, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._extract_batch(batch_audios, self.config.feature, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, feature: AudioFeature, context: ComponentActionContext) -> Dict[str, Any]:
        sample_rate = await context.render_scalar(self.config.sample_rate, int)
        fps         = await context.render_scalar(self.config.fps, int)

        if feature == AudioFeature.SPECTRUM:
            band_count      = await context.render_scalar(self.config.band_count, int)
            min_frequency   = await context.render_scalar(self.config.min_frequency, float)
            max_frequency   = await context.render_scalar(self.config.max_frequency, float)
            window_size     = await context.render_scalar(self.config.window_size, int)
            window_type     = await context.render_variable(self.config.window_type)
            frequency_scale = await context.render_variable(self.config.frequency_scale)
            normalize_mode  = await context.render_variable(self.config.normalize_mode)
            percentile      = await context.render_scalar(self.config.percentile, float)

            return {
                "sample_rate":     sample_rate,
                "fps":             fps,
                "band_count":      band_count,
                "min_frequency":   min_frequency,
                "max_frequency":   max_frequency if max_frequency is not None else sample_rate / 2,
                "window_size":     window_size,
                "window_type":     window_type,
                "frequency_scale": frequency_scale,
                "normalize_mode":  normalize_mode,
                "percentile":      percentile,
            }

        if feature == AudioFeature.WAVEFORM:
            point_count     = await context.render_scalar(self.config.point_count, int)
            window_duration = await context.render_scalar(self.config.window_duration, "time")
            summary_mode    = await context.render_variable(self.config.summary_mode)
            rectify         = await context.render_scalar(self.config.rectify, bool)

            return {
                "sample_rate":     sample_rate,
                "fps":             fps,
                "point_count":     point_count,
                "window_duration": window_duration,
                "summary_mode":    summary_mode,
                "rectify":         rectify,
            }

        raise ValueError(f"Unsupported audio feature: {feature}")

    @abstractmethod
    async def _extract_batch(
        self,
        audios: List[MediaSource],
        feature: AudioFeature,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
