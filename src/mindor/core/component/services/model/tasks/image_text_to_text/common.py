from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.utils.streamer import SyncGeneratorStreamer
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ImageTextToTextTaskAction:
    def __init__(self, config: ImageTextToTextModelActionConfig):
        self.config: ImageTextToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image         = await context.render_image(self.config.image)
        prompt        = await context.render_text(self.config.prompt)
        system_prompt = await context.render_text(self.config.system_prompt)
        batch_size    = await context.render_variable(self.config.batch_size)
        streaming     = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images, batch_prompts in BatchSourceIterator((image, prompt), batch_size=batch_size or 1):
                    batch_results = await self._generate(batch_images, batch_prompts, system_prompt, params, streaming, loop)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                                iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                                async for chunk in iterator:
                                    if chunk:
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_images, batch_prompts in BatchSourceIterator((image, prompt), batch_size=batch_size or 1):
                batch_results = await self._generate(batch_images, batch_prompts, system_prompt, params, streaming, loop)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                            iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                            async for chunk in iterator:
                                if chunk:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_output_length = await context.render_variable(self.config.params.max_output_length)
        do_sample         = await context.render_variable(self.config.params.do_sample)
        temperature       = await context.render_variable(self.config.params.temperature) if do_sample else None
        top_k             = await context.render_variable(self.config.params.top_k) if do_sample else None
        top_p             = await context.render_variable(self.config.params.top_p) if do_sample else None
        stop_sequences    = await context.render_variable(self.config.stop_sequences)

        return {
            "max_output_length": max_output_length,
            "do_sample":         do_sample,
            "temperature":       temperature,
            "top_k":             top_k,
            "top_p":             top_p,
            "stop_sequences":    stop_sequences,
        }

    @abstractmethod
    async def _generate(
        self,
        images: List[PILImage.Image],
        prompts: List[str],
        system_prompt: Optional[str],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
    ) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        pass

class ImageTextToTextTaskService(ModelTaskService):
    pass
