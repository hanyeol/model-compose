from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicSourceSeparationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from .....action.base import ComponentAction
from ...base import ComponentActionContext

if TYPE_CHECKING:
    import torch

class MusicSourceSeparationTaskAction(ComponentAction):
    def __init__(self, config: MusicSourceSeparationModelActionConfig, device: Optional[torch.device]):
        self.config: MusicSourceSeparationModelActionConfig = config
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
                    batch_results = await self._separate_batch(batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        if is_direct_output:
                            yield result
                        else:
                            context.register_source("result[]", result, scope=f"stream:{id(result)}")
                            yield await context.render_variable(self.config.output, scope=f"stream:{id(result)}")

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._separate_batch(batch_audios, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        stems       = await context.render_variable(self.config.params.stems)
        sample_rate = await context.render_variable(self.config.params.sample_rate)
        overlap     = await context.render_variable(self.config.params.overlap)
        shifts      = await context.render_variable(self.config.params.shifts)

        if isinstance(stems, str):
            stems = [ s.strip() for s in stems.split(",") if s.strip() ]

        return {
            "stems":       list(stems) if stems else [ "vocals" ],
            "sample_rate": int(sample_rate) if sample_rate is not None else None,
            "overlap":     float(overlap) if overlap is not None else None,
            "shifts":      int(shifts) if shifts is not None else None,
        }

    @abstractmethod
    async def _separate_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Any]:
        pass
