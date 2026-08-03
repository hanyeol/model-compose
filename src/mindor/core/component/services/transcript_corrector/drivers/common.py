from __future__ import annotations

from typing import Optional, Dict, List, Iterator, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TranscriptCorrectorActionConfig
from mindor.dsl.schema.action.impl.transcript_corrector.impl.common import TranscriptGranularity
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.array import ArrayValue
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class StreamingTranscriptCorrector:
    """Incremental transcript corrector interface.

    Drivers hold the pre-tokenized reference and a cursor into it. ``feed`` takes
    one STT segment at a time and yields zero or one corrected segments; ``flush``
    is a no-op for the segment-level algorithm (each segment is confirmed on
    arrival) but is kept for interface symmetry with other streaming components.
    """
    @abstractmethod
    def feed(self, segment: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        pass

    @abstractmethod
    def flush(self) -> Iterator[Dict[str, Any]]:
        pass

class TranscriptCorrectorAction(ComponentAction):
    def __init__(self, config: TranscriptCorrectorActionConfig):
        self.config: TranscriptCorrectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        transcript = await context.render_array(self.config.transcript)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(transcript, ArrayValue)
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(transcript, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_transcripts in BatchSourceIterator(transcript, batch_size=batch_size or 1):
                    batch_results = await self._correct_batch(batch_transcripts, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_transcripts in BatchSourceIterator([ transcript ] if is_single_input else transcript, batch_size=batch_size or 1):
                batch_results = await self._correct_batch(batch_transcripts, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        reference          = await context.render_text(self.config.reference)
        granularity        = await context.render_variable(self.config.granularity)
        text_key           = await context.render_variable(self.config.text_key)
        start_time_key     = await context.render_variable(self.config.start_time_key)
        end_time_key       = await context.render_variable(self.config.end_time_key)
        case_sensitive     = await context.render_scalar(self.config.case_sensitive, bool)
        ignore_punctuation = await context.render_scalar(self.config.ignore_punctuation, bool)
        window_multiplier  = await context.render_scalar(self.config.window_multiplier, float)
        min_window_tokens  = await context.render_scalar(self.config.min_window_tokens, int)
        match_threshold    = await context.render_scalar(self.config.match_threshold, float)

        if isinstance(reference, list):
            reference = " ".join(reference)

        if not reference:
            raise ValueError("'reference' must be a non-empty string")

        if granularity not in (TranscriptGranularity.WORD, TranscriptGranularity.CHARACTER, "word", "character"):
            raise ValueError(f"'granularity' must be 'word' or 'character', got {granularity!r}")

        if window_multiplier is None or window_multiplier <= 0:
            raise ValueError("'window_multiplier' must be a positive number")

        if min_window_tokens is None or min_window_tokens < 1:
            raise ValueError("'min_window_tokens' must be >= 1")

        if match_threshold is None or not (0.0 <= match_threshold <= 1.0):
            raise ValueError("'match_threshold' must be between 0.0 and 1.0")

        return {
            "reference":          reference,
            "granularity":        TranscriptGranularity(granularity) if isinstance(granularity, str) else granularity,
            "text_key":           text_key,
            "start_time_key":     start_time_key,
            "end_time_key":       end_time_key,
            "case_sensitive":     case_sensitive,
            "ignore_punctuation": ignore_punctuation,
            "window_multiplier":  window_multiplier,
            "min_window_tokens":  min_window_tokens,
            "match_threshold":    match_threshold,
        }

    async def _correct_batch(
        self,
        transcripts: List[ArrayValue],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        results: List[Any] = []

        for transcript in transcripts:
            if streaming:
                results.append(self._stream_segments(transcript, params, cancellation_token))
            else:
                results.append(await self._collect_segments(transcript, params, cancellation_token))

        return results

    async def _collect_segments(
        self,
        transcript: ArrayValue,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        async for chunk in self._stream_segments(transcript, params, cancellation_token):
            results.append(chunk)

        return results

    async def _stream_segments(
        self,
        transcript: ArrayValue,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        corrector = await self._create_corrector(params, cancellation_token)

        async for segment in transcript:
            def _feed(segment=segment) -> List[Dict[str, Any]]:
                return list(corrector.feed(segment))

            for chunk in await self._run_in_executor(_feed):
                yield chunk

        def _flush() -> List[Dict[str, Any]]:
            return list(corrector.flush())

        for chunk in await self._run_in_executor(_flush):
            yield chunk

    @abstractmethod
    async def _create_corrector(
        self,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> StreamingTranscriptCorrector:
        pass
