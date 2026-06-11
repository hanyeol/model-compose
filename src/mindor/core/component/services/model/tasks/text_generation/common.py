from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Iterator
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from mindor.core.utils.streamer import AsyncStreamer
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class TextGenerationTaskAction:
    def __init__(self, config: TextGenerationModelActionConfig):
        self.config: TextGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(text, list))
        texts: List[str] = [ text ] if is_single_input else text

        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        if streaming:
            if batch_size != 1 or len(texts) != 1:
                raise ValueError("Streaming mode only supports a single input text with batch size of 1")

            streamer = await self._generate(texts, context, streaming=True)

            async def _stream_output_generator():
                async for chunk in AsyncStreamer(streamer, loop):
                    token = chunk["choices"][0].get("text", "")
                    if token:
                        yield await self._render_output_chunk(context, token)

            return _stream_output_generator()
        else:
            results = []
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                response = await self._generate(batch_texts, context, streaming=False)
                results.extend([c["text"] for c in response["choices"]])

            result = results[0] if is_single_input else results
            return await self._render_output(context, result)

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    @abstractmethod
    async def _generate(self, texts: List[str], context: ComponentActionContext, streaming: bool) -> Union[Dict[str, Any], Iterator[Dict[str, Any]]]:
        pass

    async def _render_output_chunk(self, context: ComponentActionContext, chunk: str) -> Any:
        context.register_source("result[]", chunk)
        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else chunk

    async def _render_output(self, context: ComponentActionContext, result: Union[str, List[str]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output, convert_media=False)) if self.config.output else result

class TextGenerationTaskService(ModelTaskService):
    pass
