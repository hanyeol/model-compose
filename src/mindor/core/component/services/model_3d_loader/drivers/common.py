from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import Model3DLoaderActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.model_3d import Model3DStreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class Model3DLoaderAction(ComponentAction):
    def __init__(self, config: Model3DLoaderActionConfig, context: ComponentActionContext):
        self.config: Model3DLoaderActionConfig = config
        self.context: ComponentActionContext = context

    async def run(self) -> Any:
        source     = await self.context.render_variable(self.config.source)
        format     = await self.context.render_variable(self.config.format)
        batch_size = await self.context.render_variable(self.config.batch_size)

        params = await self._resolve_params()

        is_single_input    = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(source, (StreamIterator, AsyncIterator))
        is_direct_output   = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._load_batch(batch_sources, format, params, self.context.cancellation_token)
                    for result in batch_results:
                        self.context.register_source("result", result)
                        yield (await self.context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(source, StreamChunkIterator) and source.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Model3DStreamResource] = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._load_batch(batch_sources, format, params, self.context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            self.context.register_source("result", result)

            return (await self.context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _load_batch(
        self,
        sources: List[Any],
        format: str,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Model3DStreamResource]:
        """Load one batch of sources into Model3DStreamResource entries, one per source."""
        pass
