from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VoiceEmbeddingModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.foundation.variable.atomic import AtomicList
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class VoiceEmbedding(AtomicList):
    def __log__(self) -> str:
        return f"<VoiceEmbedding dim={len(self)}>"

class VoiceEmbeddingTaskAction(ComponentAction):
    def __init__(self, config: VoiceEmbeddingModelActionConfig):
        self.config: VoiceEmbeddingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._embed_batch(batch_audios, params, context.cancellation_token)
                    for result in batch_results:
                        yield VoiceEmbedding(result)

            return _stream_output_generator()
        else:
            results: List[VoiceEmbedding] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._embed_batch(batch_audios, params, context.cancellation_token)
                results.extend(VoiceEmbedding(result) for result in batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        normalize   = await context.render_variable(self.config.params.normalize)
        sample_rate = await context.render_scalar(self.config.params.sample_rate, int)

        return {
            "normalize":   normalize,
            "sample_rate": sample_rate,
        }

    @abstractmethod
    async def _embed_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        pass
