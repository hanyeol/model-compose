from __future__ import annotations

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SubtitleLoaderActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class SubtitleLoaderAction(ComponentAction):
    def __init__(self, config: SubtitleLoaderActionConfig):
        self.config: SubtitleLoaderActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        source     = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(source, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(source, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                    batch_results = await self._load_batch(batch_sources, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(source, StreamChunkIterator) and source.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_sources in BatchSourceIterator(source, batch_size=batch_size or 1):
                batch_results = await self._load_batch(batch_sources, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        pass

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _load_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Load one batch of sources and return one parsed subtitle entry per source.

        Each entry is either a single subtitle dict — shape: segments/full_text/
        language/format plus driver-specific extras (e.g. `is_auto_generated`) —
        or a list of such dicts when the driver produces multiple tracks per
        source (e.g. one entry per requested language).
        """
        pass
