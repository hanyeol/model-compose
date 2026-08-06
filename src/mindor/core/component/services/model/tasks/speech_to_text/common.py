from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from .....action.base import ComponentAction
from ...base import ComponentActionContext

if TYPE_CHECKING:
    import torch

class SpeechToTextTaskAction(ComponentAction):
    def __init__(self, config: SpeechToTextModelActionConfig, device: Optional[torch.device]):
        self.config: SpeechToTextModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        audio       = await context.render_audio(self.config.audio)
        batch_size  = await context.render_variable(self.config.batch_size)
        streaming   = await context.render_variable(self.config.streaming)
        time_offset = await context.render_duration(self.config.time_offset, 0.0)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._transcribe_batch(batch_audios, params, streaming, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                                async for chunk in result:
                                    if chunk:
                                        chunk = self._apply_time_offset(chunk, time_offset)
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield self._apply_time_offset(result, time_offset)

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._transcribe_batch(batch_audios, params, streaming, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(result=result, scope=f"stream:{id(result)}"):
                            async for chunk in result:
                                if chunk:
                                    chunk = self._apply_time_offset(chunk, time_offset)
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(self._apply_time_offset(result, time_offset))

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not streaming and not is_direct_output else result

    @staticmethod
    def _apply_time_offset(value: Any, offset: float) -> Any:
        """Shift `start_time` / `end_time` on a segment dict (or a list of them)
        by `offset` seconds. Non-timestamped outputs (plain strings from
        return_timestamps=False) pass through unchanged."""
        if not offset:
            return value
        if isinstance(value, dict):
            shifted = dict(value)
            if "start_time" in shifted:
                shifted["start_time"] = shifted["start_time"] + offset
            if "end_time" in shifted:
                shifted["end_time"] = shifted["end_time"] + offset
            return shifted
        if isinstance(value, list):
            return [ SpeechToTextTaskAction._apply_time_offset(item, offset) for item in value ]
        return value

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        language          = await context.render_string(self.config.language)
        return_timestamps = await context.render_scalar(self.config.return_timestamps, bool)
        timestamp_level   = await context.render_variable(self.config.timestamp_level)

        return {
            "language":          language,
            "return_timestamps": return_timestamps,
            "timestamp_level":   timestamp_level,
        }

    @abstractmethod
    async def _transcribe_batch(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[str, AsyncIterator[str], List[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]:
        pass
