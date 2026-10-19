from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction
from PIL import Image as PILImage
import asyncio

class ImageTextToTextTaskAction(ModelTaskComponentAction):
    def __init__(self, config: ImageTextToTextModelActionConfig):
        self.config: ImageTextToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        prompt        = await context.render_text(self.config.prompt)
        image         = await context.render_image_array(self.config.image, single_as_array=True, item_is_list=True) if self.config.image is not None else None
        system_prompt = await context.render_text(self.config.system_prompt)
        batch_size    = await context.render_variable(self.config.batch_size)
        streaming     = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(prompt, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_prompts, batch_images in BatchSourceIterator((prompt, image), batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_prompts, batch_images, system_prompt, params, streaming, context.cancellation_token)
                    for sequences in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(sequences=sequences, scope=f"stream:{id(sequences)}"):
                                async for chunk in self._process_sequences(sequences, streaming=True):
                                    if chunk is None:
                                        continue
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield self._process_sequences(sequences, streaming=False)

            if isinstance(prompt, StreamChunkIterator) and prompt.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_prompts, batch_images in BatchSourceIterator((prompt, image), batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_prompts, batch_images, system_prompt, params, streaming, context.cancellation_token)
                for sequences in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(sequences=sequences, scope=f"stream:{id(sequences)}"):
                            async for chunk in self._process_sequences(sequences, streaming=True):
                                if chunk is None:
                                    continue
                                context.register_source("result[]", chunk, scope=scope)
                                yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(self._process_sequences(sequences, streaming=False))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

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

    async def _generate_batch(
        self,
        prompts: List[str],
        images: List[Any],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[List[str]], List[List[AsyncIterator[str]]]]:
        images = [ (await item.collect() if item is not None else []) for item in images ]
        messages = [
            self._build_messages(prompt, len(images[index]), system_prompt)
            for index, prompt in enumerate(prompts)
        ]

        if streaming:
            return [
                self._stream(messages[index], images[index], params, cancellation_token)
                for index in range(len(prompts))
            ]

        return await asyncio.gather(*[
            self._generate(messages[index], images[index], params, cancellation_token)
            for index in range(len(prompts))
        ])

    def _process_sequences(self, sequences: Union[List[str], List[AsyncIterator[str]]], streaming: bool) -> Any:
        return sequences[0] if len(sequences) == 1 else sequences

    @abstractmethod
    async def _generate(
        self,
        messages: List[Dict[str, Any]],
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[str]:
        """Generate outputs for one (messages, images) request, returning
        `num_return_sequences` variants."""
        pass

    @abstractmethod
    def _stream(
        self,
        messages: List[Dict[str, Any]],
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[AsyncIterator[str]]:
        """Stream outputs for one (messages, images) request, returning
        `num_return_sequences` async iterators. Drivers whose native generator
        is sync should wrap it with
        SyncGeneratorStreamer(gen, asyncio.get_running_loop()) before returning."""
        pass

    @abstractmethod
    def _build_messages(self, prompt: str, image_count: int, system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        pass
