from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import CommonMusicBeatTrackingModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.variable.atomic import AtomicList
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

if TYPE_CHECKING:
    import torch

class MusicBeats(AtomicList):
    def __log__(self) -> str:
        return f"<MusicBeats count={len(self)}>"

class MusicBeatTrackingTaskAction(ComponentAction):
    def __init__(self, config: CommonMusicBeatTrackingModelActionConfig, device: Optional[torch.device]):
        self.config: CommonMusicBeatTrackingModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._track_batch(batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._track_batch(batch_audios, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        return_metadata = await context.render_scalar(self.config.return_metadata, bool)

        return {
            "return_metadata": return_metadata,
        }

    @abstractmethod
    async def _track_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
