from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Union, Optional, Dict, List, Any, Iterator
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import SpeechToTextModelActionConfig
from mindor.core.utils.iterators import AsyncSourceIterator, StreamChunkIterator
from mindor.core.utils.media import MediaSource
from mindor.core.utils.streamer import AsyncStreamer
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
import asyncio

if TYPE_CHECKING:
    import torch

class SpeechToTextTaskAction:
    def __init__(self, config: SpeechToTextModelActionConfig, device: Optional[torch.device]):
        self.config: SpeechToTextModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        audio      = await context.render_audio(self.config.audio)
        batch_size = await context.render_variable(self.config.batch_size)
        streaming  = await context.render_variable(self.config.streaming)
        params     = await self._resolve_params(context)

        is_stream_input  = isinstance(audio, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or is_stream_input

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_audios in AsyncSourceIterator(audio, batch_size=batch_size or 1):
                    batch_results = await self._transcribe(batch_audios, params, streaming=streaming)
                    for result in batch_results:
                        if streaming:
                            async for token in AsyncStreamer(result, loop):
                                if token:
                                    context.register_source("result[]", token)
                                    yield (await context.render_variable(self.config.output)) if not is_direct_output else token
                        else:
                            context.register_source("result[]", result)
                            yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()

        is_single_input: bool = not isinstance(audio, (list, AsyncIterator))
        results: List[Any] = []
        async for batch_audios in AsyncSourceIterator(audio, batch_size=batch_size or 1):
            batch_results = await self._transcribe(batch_audios, params, streaming=streaming)
            if streaming:
                results.extend([ StreamChunkIterator(AsyncStreamer(it, loop), content_type="text/plain") for it in batch_results ])
            else:
                results.extend(batch_results)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        language     = await context.render_variable(self.config.language) if self.config.language else None
        task         = await context.render_variable(self.config.task) if self.config.task is not None else None
        chunk_length = await context.render_variable(self.config.chunk_length) if self.config.chunk_length is not None else None

        return {
            "language":     language,
            "task":         task,
            "chunk_length": chunk_length,
        }

    @abstractmethod
    async def _transcribe(self, audios: List[MediaSource], params: Dict[str, Any], streaming: bool) -> Union[List[str], List[Iterator[str]]]:
        pass

class SpeechToTextTaskService(ModelTaskService):
    pass
