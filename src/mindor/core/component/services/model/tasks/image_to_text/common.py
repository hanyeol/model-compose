from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.utils.streamer import SyncGeneratorStreamer
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ImageToTextTaskAction:
    def __init__(self, config: ImageToTextModelActionConfig):
        self.config: ImageToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        prompt     = await context.render_text(self.config.prompt)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images, batch_prompts in BatchSourceIterator((image, prompt), batch_size=batch_size or 1):
                    batch_results = await self._generate(batch_images, batch_prompts, params, streaming, loop)
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
                batch_results = await self._generate(batch_images, batch_prompts, params, streaming, loop)
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
        return {}

    @abstractmethod
    async def _generate(self, images: List[PILImage.Image], prompts: Optional[List[str]], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[str], List[Union[Iterator[str], AsyncIterator[str]]]]:
        pass

class ImageToTextTaskService(ModelTaskService):
    pass
