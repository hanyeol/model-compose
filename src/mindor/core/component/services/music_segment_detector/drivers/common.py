from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicSegmentDetectorActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class MusicSegmentDetectorAction(ComponentAction):
    def __init__(self, config: MusicSegmentDetectorActionConfig):
        self.config: MusicSegmentDetectorActionConfig = config

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
        min_segment_duration = await context.render_scalar(self.config.min_segment_duration, "time")
        sample_rate          = await context.render_scalar(self.config.sample_rate, int)

        return {
            "min_segment_duration": min_segment_duration,
            "sample_rate":          sample_rate,
        }

    @staticmethod
    def _merge_short_segments(segments: List[Dict[str, Any]], min_duration: Optional[float]) -> List[Dict[str, Any]]:
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

        # Absorbing a short middle segment into its neighbour can leave two
        # adjacent same-label segments (long A + short B → A ate B, still
        # followed by long A). Collapse consecutive same-label runs so the
        # returned timeline never has an A→A transition.
        collapsed: List[Dict[str, Any]] = []
        for segment in merged:
            if collapsed and collapsed[-1]["label"] == segment["label"]:
                collapsed[-1]["end_time"] = segment["end_time"]
                continue
            collapsed.append(segment)

        return collapsed

    @abstractmethod
    async def _detect_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
