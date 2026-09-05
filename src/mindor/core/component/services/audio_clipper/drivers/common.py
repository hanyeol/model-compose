from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioClipperActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.foundation.variable.time import parse_time
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class AudioClipperAction(ComponentAction):
    def __init__(self, config: AudioClipperActionConfig):
        self.config: AudioClipperActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio            = await context.render_audio(self.config.audio)
        span             = await context.render_variable(self.config.span)
        merge            = await context.render_scalar(self.config.merge, bool, False)
        return_timestamp = await context.render_scalar(self.config.return_timestamp, bool, False)
        batch_size       = await context.render_variable(self.config.batch_size)

        # A single span dict yields a scalar clip; a list/stream yields an
        # iterator of clips. Sniff the raw shape here because ArrayValue erases
        # the dict/list distinction, and pass `is_single_span` to the driver
        # so it can produce the right per-audio shape directly.
        is_single_span = isinstance(span, dict)
        spans = ArrayValue([ span ]) if is_single_span else await context.render_array(self.config.span)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios, batch_spans in BatchSourceIterator((audio, spans), batch_size=batch_size or 1):
                    batch_results = await self._clip_batch(batch_audios, batch_spans, merge, context.cancellation_token)
                    for result in batch_results:
                        yield await self._format_result(result, merge, is_single_span, return_timestamp)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios, batch_spans in BatchSourceIterator((audio, spans), batch_size=batch_size or 1):
                batch_results = await self._clip_batch(batch_audios, batch_spans, merge, context.cancellation_token)
                for result in batch_results:
                    results.append(await self._format_result(result, merge, is_single_span, return_timestamp))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

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

    @staticmethod
    async def _format_result(result: Any, merge: bool, is_single_span: bool, return_timestamp: bool) -> Any:
        """Collapse or unwrap the driver's raw per-audio result according to
        what the caller actually asked for:
          - merge: result is `{audio, times: [...]}` (with `audio=None,
            times=[]` when the iterator produced nothing).
          - is_single_span: result is a one-element async iterator of clips;
            pull the one out.
          - otherwise: result is an async iterator of `{audio, start_time,
            end_time}` clips.
        When `return_timestamp` is off, strip the span metadata down to just
        the audio.
        """
        if merge:
            return result if return_timestamp else result["audio"]

        if is_single_span:
            first_clip: Optional[Dict[str, Any]] = None
            async for clip in result:
                first_clip = clip
                break
            if first_clip is None:
                return None
            return first_clip if return_timestamp else first_clip["audio"]

        if return_timestamp:
            return result

        async def _unwrap_audio(source=result):
            async for clip in source:
                yield clip["audio"]

        return _unwrap_audio()

    @abstractmethod
    async def _clip_batch(
        self,
        audios: List[MediaSource],
        spans: List[ArrayValue],
        merge: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[AsyncIterator[Dict[str, Any]], Dict[str, Any]]]:
        """Return, per input audio, either an async iterator of clips (per
        span, one at a time) or, when `merge=True`, a single dict of the
        stitched result. Per-span clips carry their source span as
        `{audio, start_time, end_time}`; a merged clip carries all covered
        spans as `{audio, times: [{start_time, end_time}, ...]}`. Callers
        collapse/project further as needed.
        """
        pass
