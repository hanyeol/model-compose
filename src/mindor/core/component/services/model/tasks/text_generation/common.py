from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class TextGenerationTaskAction(ComponentAction):
    def __init__(self, config: TextGenerationModelActionConfig):
        self.config: TextGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text       = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_texts, params, streaming, context.cancellation_token)
                    for sequences in batch_results:
                        yield self._wrap_result(sequences, streaming, context, is_direct_output)

            return _stream_output_generator()

        results: List[Any] = []
        async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
            batch_results = await self._generate_batch(batch_texts, params, streaming, context.cancellation_token)
            for sequences in batch_results:
                results.append(self._wrap_result(sequences, streaming, context, is_direct_output))

        context.register_source("result", results)

        return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else results

    def _wrap_result(
        self,
        sequences: Union[List[str], List[AsyncIterator[str]]],
        streaming: bool,
        context: ComponentActionContext,
        is_direct_output: bool,
    ) -> Any:
        if streaming:
            async def _stream_chunk_generator(sequences=sequences, scope=f"stream:{id(sequences)}"):
                async for chunk in self._process_result(sequences):
                    if chunk is None:
                        continue
                    context.register_source("result[]", chunk, scope=scope)
                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

            return StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)

        return self._process_result(sequences)

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_text(self.config.prompt)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length     = await context.render_variable(self.config.max_input_length)
        max_output_length    = await context.render_variable(self.config.max_output_length)
        num_return_sequences = await context.render_variable(self.config.num_return_sequences)
        do_sample            = await context.render_variable(self.config.params.do_sample)
        temperature          = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k                = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p                = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences       = await context.render_variable(self.config.stop_sequences)

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

    def _process_result(self, sequences: Union[List[str], List[AsyncIterator[str]]]) -> Any:
        """Convert one prompt's n sequences into the task's user-facing shape.

        For text-generation this passes the list through as-is (List[str] for
        non-streaming, List[AsyncIterator[str]] for streaming). Subclasses like
        chat-completion override to wrap the sequences into a `choices` envelope.
        """
        return sequences

    @abstractmethod
    async def _generate_batch(
        self,
        texts: List[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[List[str]], List[List[AsyncIterator[str]]]]:
        """Generate completions for each prompt, with `num_return_sequences` variants each.

        Contract:
          - non-streaming: returns List[List[str]] — outer list is per-prompt,
            inner list holds n completions per prompt.
          - streaming: returns List[List[AsyncIterator[str]]] — one async
            iterator per (prompt, sequence). Drivers whose native generator is
            sync should wrap it with
            SyncGeneratorStreamer(gen, asyncio.get_running_loop()) before returning.
        """
        pass
