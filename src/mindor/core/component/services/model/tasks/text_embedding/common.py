from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from ...base import ModelTaskService, ComponentActionContext

class TextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig):
        self.config: TextEmbeddingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        text = await self._prepare_input(context)
        is_single_input: bool = bool(not isinstance(text, list))
        uses_array_output: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [ text ] if is_single_input else text
        results = []

        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        async def _process():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                embeddings = await self._embed(batch_texts, context)

                if uses_array_output:
                    rendered_outputs = []
                    for embedding in embeddings:
                        rendered_outputs.append(await self._render_output_item(context, embedding))
                    yield rendered_outputs
                else:
                    yield embeddings

        if streaming:
            async def _stream_output_generator():
                async for embeddings in _process():
                    if not uses_array_output:
                        for embedding in embeddings:
                            yield await self._render_output(context, embedding)
                    else:
                        for embedding in embeddings:
                            yield embedding

            return _stream_output_generator()
        else:
            async for embeddings in _process():
                results.extend(embeddings)

            if not uses_array_output:
                result = results[0] if is_single_input else results
                return await self._render_output(context, result)
            else:
                return results

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    @abstractmethod
    async def _embed(self, texts: List[str], context: ComponentActionContext) -> List[List[float]]:
        pass

    async def _render_output_item(self, context: ComponentActionContext, embedding: List[float]) -> Any:
        context.register_source("result[]", embedding)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else embedding

    async def _render_output(self, context: ComponentActionContext, result: Union[List[float], List[List[float]]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

class TextEmbeddingTaskService(ModelTaskService):
    pass
