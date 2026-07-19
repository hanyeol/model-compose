from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SpeakerDiarizationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.core.foundation.variable.time import parse_duration
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import torch

class SpeakerDiarizationTaskAction:
    def __init__(self, config: SpeakerDiarizationModelActionConfig, device: Optional[torch.device]):
        self.config: SpeakerDiarizationModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(audio, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(audio, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._diarize(batch_audios, params, streaming, loop, context.cancellation_token)
                    for result in batch_results:
                        if streaming:
                            async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                                iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                                async for chunk in iterator:
                                    if chunk:
                                        context.register_source("result[]", chunk, scope=scope)
                                        yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                            yield StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True)
                        else:
                            yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_audios in BatchSourceIterator(audio, batch_size=batch_size or 1):
                batch_results = await self._diarize(batch_audios, params, streaming, loop, context.cancellation_token)
                for result in batch_results:
                    if streaming:
                        async def _stream_chunk_generator(generator=result, scope=f"stream:{id(result)}"):
                            iterator = generator if isinstance(generator, AsyncIterator) else SyncGeneratorStreamer(generator, loop)
                            async for chunk in iterator:
                                if chunk:
                                    context.register_source("result[]", chunk, scope=scope)
                                    yield (await context.render_variable(self.config.output, scope=scope)) if not is_direct_output else chunk

                        results.append(StreamChunkIterator(_stream_chunk_generator(), is_fragmented=True))
                    else:
                        results.append(result)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        sample_rate          = await context.render_variable(self.config.sample_rate)
        num_speakers         = await context.render_variable(self.config.params.num_speakers) if self.config.params.num_speakers is not None else None
        min_speakers         = await context.render_variable(self.config.params.min_speakers) if self.config.params.min_speakers is not None else None
        max_speakers         = await context.render_variable(self.config.params.max_speakers) if self.config.params.max_speakers is not None else None
        min_segment_duration = await context.render_variable(self.config.params.min_segment_duration)
        merge_gap            = await context.render_variable(self.config.params.merge_gap)

        return {
            "sample_rate":          int(sample_rate),
            "num_speakers":         int(num_speakers) if num_speakers is not None else None,
            "min_speakers":         int(min_speakers) if min_speakers is not None else None,
            "max_speakers":         int(max_speakers) if max_speakers is not None else None,
            "min_segment_duration": parse_duration(min_segment_duration),
            "merge_gap":            parse_duration(merge_gap),
        }

    @abstractmethod
    async def _diarize(
        self,
        audios: List[MediaSource],
        params: Dict[str, Any],
        streaming: bool,
        loop: asyncio.AbstractEventLoop,
        cancellation_token: Optional[CancellationToken] = None
    ) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        pass

class SpeakerDiarizationTaskService(ModelTaskService):
    pass
