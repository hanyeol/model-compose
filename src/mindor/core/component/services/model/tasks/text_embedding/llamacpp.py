from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.action import ModelActionConfig, TextEmbeddingModelActionConfig
from mindor.core.logger import logging
from ...base import ModelTaskType, ModelDriver, register_model_task_service
from ...base import LlamaCppModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    from llama_cpp import Llama

class LlamaCppTextEmbeddingTaskAction:
    def __init__(
        self,
        config: TextEmbeddingModelActionConfig,
        model: Llama,
    ):
        self.config: TextEmbeddingModelActionConfig = config
        self.model: Llama = model

    async def run(self, context: ComponentActionContext) -> Any:
        text = await self._prepare_input(context)
        is_single_input: bool = not isinstance(text, list)
        uses_array_output: bool = context.contains_variable_reference("result[]", self.config.output)
        texts: List[str] = [text] if is_single_input else text

        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)
        normalize  = await context.render_variable(self.config.params.normalize)

        async def _embed():
            for index in range(0, len(texts), batch_size):
                batch_texts = texts[index:index + batch_size]
                embeddings = self._embed_batch(batch_texts, normalize)

                if uses_array_output:
                    rendered_outputs = []
                    for embedding in embeddings:
                        rendered_outputs.append(await self._render_output_item(context, embedding))
                    yield rendered_outputs
                else:
                    yield embeddings

        if streaming:
            async def _stream_output_generator():
                async for embeddings in _embed():
                    if not uses_array_output:
                        for embedding in embeddings:
                            yield await self._render_output(context, embedding)
                    else:
                        for embedding in embeddings:
                            yield embedding

            return _stream_output_generator()
        else:
            results = []
            async for embeddings in _embed():
                results.extend(embeddings)

            if not uses_array_output:
                result = results[0] if is_single_input else results
                return await self._render_output(context, result)
            else:
                return results

    def _embed_batch(self, texts: List[str], normalize: bool) -> List[List[float]]:
        import math

        embeddings = self.model.embed(texts)

        if normalize:
            normalized = []
            for emb in embeddings:
                norm = math.sqrt(sum(x * x for x in emb))
                if norm > 1e-12:
                    normalized.append([x / norm for x in emb])
                else:
                    normalized.append(emb)
            return normalized

        return embeddings

    async def _prepare_input(self, context: ComponentActionContext) -> Union[str, List[str]]:
        return await context.render_variable(self.config.text)

    async def _render_output_item(self, context: ComponentActionContext, embedding: List[float]) -> Any:
        context.register_source("result[]", embedding)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else embedding

    async def _render_output(self, context: ComponentActionContext, result: Union[List[float], List[List[float]]]) -> Any:
        context.register_source("result", result)
        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result


@register_model_task_service(ModelTaskType.TEXT_EMBEDDING, ModelDriver.LLAMACPP)
class LlamaCppTextEmbeddingTaskService(LlamaCppModelTaskService):
    def _load_model(self) -> None:
        from llama_cpp import Llama

        model_path = self._get_model_path()
        params = self._get_model_params()
        params["embedding"] = True

        logging.info(f"Component '{self.id}': loading llama.cpp embedding model from '{model_path}'")
        self.model = Llama(model_path=model_path, **params)

    async def _run(
        self,
        action: ModelActionConfig,
        context: ComponentActionContext,
        loop: asyncio.AbstractEventLoop
    ) -> Any:
        return await LlamaCppTextEmbeddingTaskAction(action, self.model).run(context)
