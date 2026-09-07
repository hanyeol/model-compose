from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageTextToTextModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class ImageTextToTextTaskAction(ComponentAction):
    def __init__(self, config: ImageTextToTextModelActionConfig):
        self.config: ImageTextToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        messages, images = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(messages, list) and (len(messages) == 0 or isinstance(messages[0], dict))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        source_messages = [messages] if is_single_input else messages
        source_images   = [images] if is_single_input else images

        if isinstance(messages, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_messages, batch_images in BatchSourceIterator((source_messages, source_images), batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_messages, batch_images, params, streaming, context.cancellation_token)
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
            async for batch_messages, batch_images in BatchSourceIterator((source_messages, source_images), batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_messages, batch_images, params, streaming, context.cancellation_token)
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

    async def _prepare_input(
        self, context: ComponentActionContext
    ) -> Tuple[
        Union[
            List[Dict[str, Any]],
            List[List[Dict[str, Any]]],
            AsyncIterator[List[Dict[str, Any]]]
        ],
        Union[
            List[PILImage.Image],
            List[List[PILImage.Image]],
            AsyncIterator[List[PILImage.Image]]
        ]
    ]:
        prompt        = await context.render_text(self.config.prompt)
        image         = await context.render_image_array(self.config.image, single_as_array=True)
        system_prompt = await context.render_text(self.config.system_prompt)

        is_single_input = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        images = await self._resolve_images(image, is_single_input)

        if isinstance(prompt, (StreamIterator, AsyncIterator)):
            async def _iterate_messages(prompts, images):
                async for prompt, images in zip(prompts, images):
                    yield self._build_messages(prompt, len(images), system_prompt)

            return _iterate_messages(prompt, images), images

        if isinstance(prompt, list):
            messages = [
                self._build_messages(prompt, len(images), system_prompt)
                for prompt, images in zip(prompt, images)
            ]

            return messages, images

        return self._build_messages(prompt, len(images[0]), system_prompt), images[0]

    async def _resolve_images(
        self,
        image: Optional[Union[ImageArrayValue, List[Optional[ImageArrayValue]], AsyncIterator[Optional[ImageArrayValue]]]],
        is_single_input: bool,
    ) -> Union[List[List[PILImage.Image]], AsyncIterator[Optional[ImageArrayValue]]]:
        if is_single_input:
            return [ await image.collect() ] if image is not None else [ [] ]

        if isinstance(image, list):
            return [ (await item.collect() if item is not None else []) for item in image ]

        return image

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
        messages: List[List[Dict[str, Any]]],
        images: List[List[PILImage.Image]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> Union[List[str], List[AsyncIterator[str]]]:
        pass

    @abstractmethod
    def _build_messages(self, prompt: str, image_count: int, system_prompt: Optional[str]) -> List[Dict[str, Any]]:
        pass
