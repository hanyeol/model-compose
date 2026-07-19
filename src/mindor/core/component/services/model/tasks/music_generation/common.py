from __future__ import annotations

from typing import Optional, Dict, Any, List
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
import asyncio

class MusicGenerationTaskAction:
    def __init__(self, config: MusicGenerationModelActionConfig):
        self.config: MusicGenerationModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        prompt     = await context.render_text(self.config.prompt)
        lyrics     = await context.render_text(self.config.lyrics) if self.config.lyrics is not None else None
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(prompt, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_prompts, batch_lyrics in BatchSourceIterator((prompt, lyrics), batch_size=batch_size or 1):
                    batch_results = self._generate(batch_prompts, batch_lyrics, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Any] = []
            async for batch_prompts, batch_lyrics in BatchSourceIterator((prompt, lyrics), batch_size=batch_size or 1):
                batch_results = self._generate(batch_prompts, batch_lyrics, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        duration  = await context.render_variable(self.config.params.duration)
        bpm       = await context.render_variable(self.config.params.bpm)
        key_scale = await context.render_variable(self.config.params.key_scale)

        return {
            "duration":  duration,
            "bpm":       bpm,
            "key_scale": key_scale,
        }

    @abstractmethod
    def _generate(
        self,
        prompts: List[str],
        lyrics: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Any]:
        pass

class MusicGenerationTaskService(ModelTaskService):
    pass
