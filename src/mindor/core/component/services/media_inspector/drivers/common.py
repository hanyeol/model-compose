from __future__ import annotations

from typing import Optional, Dict, List, Any

from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ....action.base import ComponentAction
from ..base import ComponentActionContext

class MediaInspectorAction(ComponentAction):
    def __init__(self, config: MediaInspectorActionConfig):
        self.config: MediaInspectorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        media      = await context.render_media(self.config.media)
        return_raw = await context.render_scalar(self.config.return_raw, bool, True)
        batch_size = await context.render_variable(self.config.batch_size)

        is_single_input  = not isinstance(media, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(media, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_sources in BatchSourceIterator(media, batch_size=batch_size or 1):
                    batch_results = await self._inspect_batch(batch_sources, return_raw, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_sources in BatchSourceIterator(media, batch_size=batch_size or 1):
                batch_results = await self._inspect_batch(batch_sources, return_raw, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    @abstractmethod
    async def _inspect_batch(
        self,
        sources: List[MediaSource],
        return_raw: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        """Return, per input source, a normalized metadata dict.

        Each `MediaSource` carries the caller's format/attrs hints. When
        `return_raw` is true the driver's raw output should be included
        under `raw` in each result.
        """
        pass
