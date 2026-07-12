from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class TextEmbeddingTaskAction:
    def __init__(self, config: TextEmbeddingModelActionConfig):
        self.config: TextEmbeddingModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        text       = await context.render_text(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(text, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(text, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                    batch_results = await self._embed(batch_texts, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[List[float]] = []
            async for batch_texts in BatchSourceIterator(text, batch_size=batch_size or 1):
                batch_results = await self._embed(batch_texts, params, loop)
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
    async def _embed(self, texts: List[str], params: Dict[str, Any], loop: asyncio.AbstractEventLoop) -> List[List[float]]:
        pass

class TextEmbeddingTaskService(ModelTaskService):
    pass
