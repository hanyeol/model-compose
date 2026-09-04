from __future__ import annotations

from typing import Optional, Union, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from mindor.dsl.schema.action.impl.music_analyzer.impl.common import MusicAnalyzerMetric
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicDict
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext
import asyncio

class MusicBeats(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<MusicBeats bpm={self.get('bpm')} "
            f"confidence={self.get('confidence')} "
            f"count={len(self.get('beats', []))}>"
        )

class MusicOnsets(AtomicDict):
    def __log__(self) -> str:
        return f"<MusicOnsets count={len(self.get('onsets', []))}>"

class MusicTempogram(AtomicDict):
    def __log__(self) -> str:
        frames = self.get("frames", [])
        rows = len(frames[0]) if frames else 0

        return (
            f"<MusicTempogram frames={len(frames)}x{rows} "
            f"fps={self.get('fps')} sample_rate={self.get('sample_rate')}>"
        )

class MusicActivity(AtomicDict):
    def __log__(self) -> str:
        return f"<MusicActivity regions={len(self.get('activity', []))}>"

class MusicChroma(AtomicDict):
    def __log__(self) -> str:
        frames = self.get("frames", [])
        rows = len(frames[0]) if frames else 0

        return (
            f"<MusicChroma frames={len(frames)}x{rows} "
            f"fps={self.get('fps')} sample_rate={self.get('sample_rate')}>"
        )

class MusicTonnetz(AtomicDict):
    def __log__(self) -> str:
        frames = self.get("frames", [])
        rows = len(frames[0]) if frames else 0

        return (
            f"<MusicTonnetz frames={len(frames)}x{rows} "
            f"fps={self.get('fps')} sample_rate={self.get('sample_rate')}>"
        )

class MusicBrightness(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<MusicBrightness mean_hz={self.get('brightness_hz')} "
            f"frames={len(self.get('frames', []))} "
            f"fps={self.get('fps')} sample_rate={self.get('sample_rate')}>"
        )

class MusicFlatness(AtomicDict):
    def __log__(self) -> str:
        return (
            f"<MusicFlatness mean={self.get('flatness')} "
            f"frames={len(self.get('frames', []))} "
            f"fps={self.get('fps')} sample_rate={self.get('sample_rate')}>"
        )

class MusicAnalyzerAction(ComponentAction):
    def __init__(self, config: MusicAnalyzerActionConfig):
        self.config: MusicAnalyzerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source     = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.metric, context)

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._analyze_batch(batch, self.config.metric, params, context.cancellation_token)
                    for analysis in batch_results:
                        yield analysis

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._analyze_batch(batch, self.config.metric, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        """Resolve whichever of `audio` / `spectrum` was provided into a single
        source stream.
        """
        audio    = await context.render_audio(self.config.audio) if self.config.audio is not None else None
        spectrum = await context.render_variable(self.config.spectrum) if self.config.spectrum is not None else None

        if audio is None and spectrum is None:
            raise ValueError("Either `audio` or `spectrum` must be provided.")

        return audio if audio is not None else spectrum

    async def _resolve_params(self, metric: MusicAnalyzerMetric, context: ComponentActionContext) -> Dict[str, Any]:
        sample_rate = await context.render_scalar(self.config.sample_rate, int)

        if metric == MusicAnalyzerMetric.BEATS:
            min_bpm = await context.render_scalar(self.config.min_bpm, float)
            max_bpm = await context.render_scalar(self.config.max_bpm, float)

            return {
                "sample_rate": sample_rate,
                "min_bpm":     min_bpm,
                "max_bpm":     max_bpm,
            }

        if metric == MusicAnalyzerMetric.ONSETS:
            min_gap = await context.render_scalar(self.config.min_gap, "time")

            return {
                "sample_rate": sample_rate,
                "min_gap":     min_gap,
            }

        if metric == MusicAnalyzerMetric.TEMPOGRAM:
            min_bpm = await context.render_scalar(self.config.min_bpm, float)
            max_bpm = await context.render_scalar(self.config.max_bpm, float)

            return {
                "sample_rate": sample_rate,
                "min_bpm":     min_bpm,
                "max_bpm":     max_bpm,
            }

        if metric == MusicAnalyzerMetric.ACTIVITY:
            min_duration = await context.render_scalar(self.config.min_duration, "time")
            level        = await context.render_scalar(self.config.level, float)

            return {
                "sample_rate":  sample_rate,
                "min_duration": min_duration,
                "level":        level,
            }

        if metric == MusicAnalyzerMetric.KEY:
            return {
                "sample_rate": sample_rate,
            }

        if metric == MusicAnalyzerMetric.CHROMA:
            return {
                "sample_rate": sample_rate,
            }

        if metric == MusicAnalyzerMetric.TONNETZ:
            return {
                "sample_rate": sample_rate,
            }

        if metric == MusicAnalyzerMetric.BRIGHTNESS:
            return {
                "sample_rate": sample_rate,
            }

        if metric == MusicAnalyzerMetric.FLATNESS:
            return {
                "sample_rate": sample_rate,
            }

        if metric == MusicAnalyzerMetric.HARMONICITY:
            return {
                "sample_rate": sample_rate,
            }

        raise ValueError(f"Unsupported music metric: {metric}")

    async def _analyze_batch(
        self,
        sources: List[Union[MediaSource, Dict[str, Any]]],
        metric: MusicAnalyzerMetric,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        return await asyncio.gather(*[
            self._analyze(metric, source, params, cancellation_token) for source in sources
        ])

    async def _analyze(
        self,
        metric: MusicAnalyzerMetric,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Dict[str, Any]:
        if metric == MusicAnalyzerMetric.BEATS:
            return await self._analyze_beats(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.ONSETS:
            return await self._analyze_onsets(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.TEMPOGRAM:
            return await self._analyze_tempogram(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.ACTIVITY:
            return await self._analyze_activity(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.KEY:
            return await self._analyze_key(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.CHROMA:
            return await self._analyze_chroma(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.TONNETZ:
            return await self._analyze_tonnetz(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.BRIGHTNESS:
            return await self._analyze_brightness(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.FLATNESS:
            return await self._analyze_flatness(source, params, cancellation_token)

        if metric == MusicAnalyzerMetric.HARMONICITY:
            return await self._analyze_harmonicity(source, params, cancellation_token)

        raise ValueError(f"Unsupported music metric: {metric}")

    @abstractmethod
    async def _analyze_beats(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_onsets(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_tempogram(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_activity(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_key(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_chroma(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_tonnetz(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_brightness(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_flatness(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def _analyze_harmonicity(
        self,
        source: Union[MediaSource, Dict[str, Any]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken],
    ) -> Dict[str, Any]:
        pass
