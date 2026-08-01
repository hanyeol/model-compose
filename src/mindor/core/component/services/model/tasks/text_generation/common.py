from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from .....action.base import ComponentAction
from ...base import ModelTaskService, ComponentActionContext

class TextGenerationTaskAction(ComponentAction):
    def __init__(self, config: TextGenerationModelActionConfig):
        self.config: TextGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text       = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_texts, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    if chunk:
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_texts, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                if chunk:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_text(self.config.prompt)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length     = await context.render_variable(self.config.max_input_length)
        max_output_length    = await context.render_variable(self.config.max_output_length)
        num_return_sequences = await context.render_variable(self.config.params.num_return_sequences)
        do_sample            = await context.render_variable(self.config.params.do_sample)
        temperature          = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k                = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p                = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences       = await context.render_variable(self.config.params.stop_sequences)

        return {
            "max_input_length":     max_input_length,
            "max_output_length":    max_output_length,
            "num_return_sequences": num_return_sequences,
            "do_sample":            do_sample,
            "temperature":          temperature,
            "top_k":                top_k,
            "top_p":                top_p,
            "stop_sequences":       stop_sequences,
        }

    @abstractmethod
    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        """Generate text (or streaming chunks) for each prompt.

        Contract:
          - non-streaming: returns List[str], one completion per prompt.
          - streaming: returns List[AsyncIterator[str]], one async iterator per prompt.
            Drivers whose native generator is sync should wrap it with
            SyncGeneratorStreamer(gen, asyncio.get_running_loop()) before returning.
        """
        pass

class TextGenerationTaskService(ModelTaskService):
    pass
