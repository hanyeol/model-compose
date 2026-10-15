from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicScoreRendererActionConfig
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class MusicScoreRendererAction(ComponentAction):
    def __init__(self, config: MusicScoreRendererActionConfig, context: ComponentActionContext):
        self.config: MusicScoreRendererActionConfig = config
        self.context: ComponentActionContext = context

    async def run(self) -> Any:
        source     = await self._prepare_input()
        batch_size = await self.context.render_variable(self.config.batch_size)

        params = await self._resolve_params()

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._render_batch(batch_sources, params, self.context.cancellation_token)
                    for result in batch_results:
                        self.context.register_source("result", result)
                        yield (await self.context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(source, StreamChunkIterator) and source.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[List[StreamResource]] = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._render_batch(batch_sources, params, self.context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            self.context.register_source("result", result)

            return (await self.context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _prepare_input(self) -> Any:
        pass

    async def _resolve_params(self) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _render_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[StreamResource]]:
        """Render one batch of score sources.

        Each returned entry is the list of per-page outputs for one source
        (one StreamResource per page, in page order).
        """
        pass
