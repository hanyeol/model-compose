from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VoiceActivityDetectionModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamChunkIterator, StreamIterator
from mindor.core.foundation.streaming.media import MediaSource
from mindor.core.utils.streamer import SyncGeneratorStreamer
from mindor.core.foundation.variable.time import parse_duration
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import torch

class VoiceActivityDetectionTaskAction:
    def __init__(self, config: VoiceActivityDetectionModelActionConfig, device: Optional[torch.device]):
        self.config: VoiceActivityDetectionModelActionConfig = config
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
                    batch_results = await self._detect(batch_audios, params, streaming, loop)
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
                batch_results = await self._detect(batch_audios, params, streaming, loop)
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
        threshold            = await context.render_variable(self.config.params.threshold)
        min_speech_duration  = parse_duration(await context.render_variable(self.config.params.min_speech_duration))
        min_silence_duration = parse_duration(await context.render_variable(self.config.params.min_silence_duration))
        speech_padding_time  = parse_duration(await context.render_variable(self.config.params.speech_padding_time))

        return {
            "sample_rate":          sample_rate,
            "threshold":            threshold,
            "min_speech_duration":  min_speech_duration,
            "min_silence_duration": min_silence_duration,
            "speech_padding_time":  speech_padding_time,
        }

    @abstractmethod
    async def _detect(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool, loop: asyncio.AbstractEventLoop) -> Union[List[List[Dict[str, Any]]], List[Union[Iterator[Dict[str, Any]], AsyncIterator[Dict[str, Any]]]]]:
        pass

class VoiceActivityDetectionTaskService(ModelTaskService):
    pass
