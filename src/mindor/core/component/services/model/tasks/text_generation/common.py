from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.core.utils.iterators import BatchSourceIterator, StreamChunkIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class TextGenerationTaskAction:
    def __init__(self, config: TextGenerationModelActionConfig):
        self.config: TextGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        is_single_input  = not isinstance(text, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, AsyncIterator):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._generate(batch_texts, context, streaming, loop)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(streamer=result, scope=f"stream:{id(result)}"):
                                async for chunk in SyncGeneratorStreamer(streamer, loop):
                                    if chunk:
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), content_type="text/plain")
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._generate(batch_texts, context, streaming, loop)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(streamer=result, scope=f"stream:{id(result)}"):
                            async for chunk in SyncGeneratorStreamer(streamer, loop):
                                if chunk:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), content_type="text/plain"))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_text(self.config.text)

    @abstractmethod
    async def _generate(self, texts: List[str], context: ComponentActionContext, streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Iterator[str]]]:
        pass

class TextGenerationTaskService(ModelTaskService):
    pass
