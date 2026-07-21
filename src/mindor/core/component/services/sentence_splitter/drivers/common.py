from __future__ import annotations

from typing import Optional, Dict, List, Iterator, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SentenceSplitterActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator, TextDecodeIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.text import TextStreamResource
from mindor.core.logger import logging
from ..base import ComponentActionContext
import asyncio

class StreamingSentenceSplitter:
    """Incremental sentence splitter driver interface.

    Drivers hold a pending buffer of received text and emit complete chunks as
    input arrives. ``feed`` yields whatever is safe to emit given the current
    buffer state; ``flush`` yields the remainder (called when the input stream
    ends).
    """
    @abstractmethod
    def feed(self, text: str) -> Iterator[str]:
        pass

    @abstractmethod
    def flush(self) -> Iterator[str]:
        pass

class SentenceSplitterAction:
    def __init__(self, config: SentenceSplitterActionConfig):
        self.config: SentenceSplitterActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await context.render_text(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_texts, params, streaming, loop, context.cancellation_token)
                    for result in batch_results:
                        if isinstance(result, (StreamIterator, AsyncIterator)):
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
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_texts, params, streaming, loop, context.cancellation_token)
                for result in batch_results:
                    if isinstance(result, (StreamIterator, AsyncIterator)):
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=False))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        min_chunk_length = await context.render_variable(self.config.min_chunk_length)
        max_chunk_length = await context.render_variable(self.config.max_chunk_length) if self.config.max_chunk_length is not None else None

        if min_chunk_length is None or min_chunk_length < 0:
            raise ValueError("'min_chunk_length' must be a non-negative integer")

        if max_chunk_length is not None and max_chunk_length <= 0:
            raise ValueError("'max_chunk_length' must be a positive integer when set")

        if max_chunk_length is not None and max_chunk_length < min_chunk_length:
            raise ValueError(f"'max_chunk_length' ({max_chunk_length}) must be >= 'min_chunk_length' ({min_chunk_length})")

        return { "min_chunk_length": min_chunk_length, "max_chunk_length": max_chunk_length }

    async def _process_batch(
        self,
        texts: List[Any],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        return await asyncio.gather(*[
            self._process(text, params, streaming, loop, cancellation_token) for text in texts
        ])

    async def _process(
        self,
        text: Any,
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Any:
        if text is None:
            logging.debug("Sentence splitter skipped because no text was provided.")
            return None

        if streaming:
            return self._stream_sentences(text, params["min_chunk_length"], params["max_chunk_length"], cancellation_token)

        return await self._collect_sentences(text, params["min_chunk_length"], params["max_chunk_length"], cancellation_token)

    async def _collect_sentences(
        self,
        text: Any,
        min_chunk_length: int,
        max_chunk_length: Optional[int],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[str]:
        results: List[str] = []

        async for chunk in self._stream_sentences(text, min_chunk_length, max_chunk_length, cancellation_token):
            results.append(chunk)

        return results

    async def _stream_sentences(
        self,
        text: Any,
        min_chunk_length: int,
        max_chunk_length: Optional[int],
        cancellation_token: Optional[CancellationToken] = None
    ) -> AsyncIterator[str]:
        splitter = self._create_splitter(min_chunk_length, max_chunk_length)

        if isinstance(text, TextStreamResource):
            text = text.text

        if isinstance(text, (StreamResource, StreamChunkIterator)):
            async for piece in TextDecodeIterator(text):
                for chunk in splitter.feed(piece):
                    yield chunk
        else:
            for chunk in splitter.feed(text):
                yield chunk

        for chunk in splitter.flush():
            yield chunk

    @abstractmethod
    def _create_splitter(self, min_chunk_length: int, max_chunk_length: Optional[int]) -> StreamingSentenceSplitter:
        pass
