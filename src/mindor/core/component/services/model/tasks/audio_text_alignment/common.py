from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import AudioTextAlignmentModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from .....action.base import ComponentAction
from ...base import ComponentActionContext

if TYPE_CHECKING:
    import torch

class AudioTextAlignmentTaskAction(ComponentAction):
    def __init__(self, config: AudioTextAlignmentModelActionConfig, device: Optional[torch.device]):
        self.config: AudioTextAlignmentModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        audio      = await context.render_audio(self.config.audio)
        text       = await context.render_text(self.config.text)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios, batch_texts in BatchSourceIterator((audio, text), batch_size=batch_size or 1):
                    batch_results = await self._align_batch(batch_audios, batch_texts, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[List[Dict[str, Any]]] = []
            async for batch_audios, batch_texts in BatchSourceIterator((audio, text), batch_size=batch_size or 1):
                batch_results = await self._align_batch(batch_audios, batch_texts, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        language          = await context.render_string(self.config.language)
        chunk_length      = await context.render_duration(self.config.chunk_length)
        chunk_overlap     = await context.render_duration(self.config.chunk_overlap)
        return_confidence = await context.render_scalar(self.config.return_confidence, bool)

        if chunk_overlap >= chunk_length:
            raise ValueError(f"'chunk_overlap' ({chunk_overlap}s) must be smaller than 'chunk_length' ({chunk_length}s).")

        return {
            "language":          language,
            "chunk_length":      chunk_length,
            "chunk_overlap":     chunk_overlap,
            "return_confidence": return_confidence,
        }

    @abstractmethod
    async def _align_batch(
        self,
        audios: List[MediaSource],
        texts: List[str],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[Dict[str, Any]]]:
        pass
