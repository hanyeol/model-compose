from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class ImageToTextTaskAction(ComponentAction):
    def __init__(self, config: ImageToTextModelActionConfig):
        self.config: ImageToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
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
                    batch_results = await self._generate_batch(batch_images, batch_prompts, params, streaming, context.cancellation_token)
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
            async for batch_images, batch_prompts in BatchSourceIterator((image, prompt), batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_images, batch_prompts, params, streaming, context.cancellation_token)
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

    @abstractmethod
    async def _generate_batch(
        self,
        images: List[PILImage.Image],
        prompts: Optional[List[str]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        pass
