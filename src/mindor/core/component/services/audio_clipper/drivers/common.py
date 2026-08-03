from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioClipperActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.time import parse_time
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.audio import AudioStreamResource
from mindor.core.foundation.streaming.media import MediaSource
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class AudioClipperAction(ComponentAction):
    def __init__(self, config: AudioClipperActionConfig):
        self.config: AudioClipperActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        span       = await context.render_variable(self.config.span)
        merge      = await context.render_scalar(self.config.merge, bool, False)
        batch_size = await context.render_variable(self.config.batch_size)

        # A single span dict collapses the per-audio result into a scalar clip;
        # a list returns the iterator as-is. Sniff the raw shape here because
        # ArrayValue erases the dict/list distinction.
        is_single_span = isinstance(span, dict)
        spans = ArrayValue([ span ]) if is_single_span else await context.render_array(self.config.span)

        is_single_output = is_single_span or merge
        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios, batch_spans in BatchSourceIterator((audio, spans), batch_size=batch_size or 1):
                    batch_results = await self._clip_batch(batch_audios, batch_spans, merge, context.cancellation_token)
                    for result in batch_results:
                        yield await self._collapse(result) if is_single_output else result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios, batch_spans in BatchSourceIterator((audio, spans), batch_size=batch_size or 1):
                batch_results = await self._clip_batch(batch_audios, batch_spans, merge, context.cancellation_token)
                for result in batch_results:
                    results.append(await self._collapse(result) if is_single_output else result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @staticmethod
    async def _collapse(clips: AsyncIterator[AudioStreamResource]) -> AudioStreamResource:
        """Pull the single clip out of a one-element iterator produced by _clip_batch."""
        first: Optional[AudioStreamResource] = None
        async for clip in clips:
            if first is not None:
                raise RuntimeError("expected a single clip but the iterator produced more than one")
            first = clip
        if first is None:
            raise ValueError("'span' must contain at least one entry")
        return first

    @staticmethod
    async def _iterate_spans(spans: ArrayValue) -> AsyncIterator[Dict[str, float]]:
        """Yield parsed/validated spans lazily so an ArrayValue backed by an async
        iterator can be consumed without materializing the full list."""
        async for span in spans:
            if not isinstance(span, dict):
                raise ValueError(f"Each span must be an object with start_time/end_time, got {type(span).__name__}")

            start_time = parse_time(span["start_time"])
            end_time   = parse_time(span["end_time"])

            if end_time <= start_time:
                raise ValueError(f"span end_time ({end_time}) must be greater than start_time ({start_time})")

            yield { "start_time": start_time, "end_time": end_time }

    @abstractmethod
    async def _clip_batch(
        self,
        audios: List[MediaSource],
        spans: List[ArrayValue],
        merge: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AsyncIterator[AudioStreamResource]]:
        """Return, per input audio, an async iterator of clips."""
        pass
