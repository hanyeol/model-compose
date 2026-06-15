from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from mindor.core.utils.iterators import AsyncSourceIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class TextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig):
        self.config: TextEmbeddingModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await context.render_variable(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)
        params     = await self._resolve_params(context)

        is_stream_input  = isinstance(text, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or is_stream_input

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_texts in AsyncSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._embed(batch_texts, params)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()

        is_single_input: bool = not isinstance(text, (list, AsyncIterator))
        results: List[List[float]] = []
        async for batch_texts in AsyncSourceIterator(text, batch_size=batch_size or 1):
            batch_results = await self._embed(batch_texts, params)
            results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        max_input_length = await context.render_variable(self.config.max_input_length) if self.config.max_input_length is not None else None
        pooling          = await context.render_variable(self.config.params.pooling)
        normalize        = await context.render_variable(self.config.params.normalize)

        return {
            "max_input_length": max_input_length,
            "pooling":          pooling,
            "normalize":        normalize,
        }

    @abstractmethod
    async def _embed(self, texts: List[str], params: Dict[str, Any]) -> List[List[float]]:
        pass

class TextEmbeddingTaskService(ModelTaskService):
    pass
