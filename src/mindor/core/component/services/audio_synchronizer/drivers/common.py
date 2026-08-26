from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioSynchronizerActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.media import MediaArrayValue
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class AudioSynchronizerAction(ComponentAction):
    def __init__(self, config: AudioSynchronizerActionConfig):
        self.config: AudioSynchronizerActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        sources    = await context.render_media_array(self.config.sources, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(sources, MediaArrayValue) and sources.is_single
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(sources, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(sources, batch_size=batch_size or 1):
                    batch_results = await self._synchronize_batch(batch_sources, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[List[Dict[str, Any]]] = []
            async for batch_sources in BatchSourceIterator(sources, batch_size=batch_size or 1):
                batch_results = await self._synchronize_batch(batch_sources, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return {}

    @abstractmethod
    async def _synchronize_batch(
        self,
        sources: List[MediaArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Dict[str, Any]]]:
        pass
