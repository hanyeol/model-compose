from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import ImageToTextModelActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ImageToTextTaskAction:
    def __init__(self, config: ImageToTextModelActionConfig):
        self.config: ImageToTextModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image, text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(image, list))
        images: List[PILImage.Image] = [ image ] if is_single_input else image
        texts: Optional[List[str]] = [ text ] if is_single_input else text

        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        if streaming:
            if batch_size != 1 or len(images) != 1:
                raise ValueError("Streaming mode only supports a single input image with batch size of 1")

            streamer = await self._generate(images, texts, context, streaming=True)

            async def _stream_output_generator():
                async for chunk in AsyncStreamer(streamer, loop):
                    if chunk:
                        yield await self._render_output_chunk(context, chunk)

            return _stream_output_generator()
        else:
            results = []
            for index in range(0, len(images), batch_size):
                batch_images = images[index:index + batch_size]
                batch_texts = texts[index:index + batch_size] if texts else None
                outputs = await self._generate(batch_images, batch_texts, context, streaming=False)
                results.extend(outputs)

            result = results[0] if is_single_input else results
            return await self._render_output(context, result)

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Union[PILImage.Image, List[PILImage.Image]], Optional[Union[str, List[str]]]]:
        image = await context.render_image(self.config.image)
        text  = await context.render_variable(self.config.text)

        return image, text

    @abstractmethod
    async def _generate(self, images: List[PILImage.Image], texts: Optional[List[str]], context: ComponentActionContext, streaming: bool) -> Union[List[str], Iterator[str]]:
        pass

    async def _render_output_chunk(self, context: ComponentActionContext, chunk: str) -> Any:
        context.register_source("result[]", chunk)
        return (await context.render_variable(self.config.output)) if self.config.output else chunk

    async def _render_output(self, context: ComponentActionContext, result: Union[str, List[str]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output)) if self.config.output else result

class ImageToTextTaskService(ModelTaskService):
    pass
