from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextToVideoModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class TextToVideoTaskAction(ComponentAction):
    def __init__(self, config: TextToVideoModelActionConfig):
        self.config: TextToVideoModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        prompt          = await context.render_text(self.config.prompt)
        negative_prompt = await context.render_text(self.config.negative_prompt) if self.config.negative_prompt is not None else None
        batch_size      = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(prompt, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_prompts, batch_negatives in BatchSourceIterator((prompt, negative_prompt), batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_prompts, batch_negatives, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_prompts, batch_negatives in BatchSourceIterator((prompt, negative_prompt), batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_prompts, batch_negatives, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_frames = await context.render_variable(self.config.params.num_frames)
        fps        = await context.render_variable(self.config.params.fps)
        height     = await context.render_variable(self.config.params.height)
        width      = await context.render_variable(self.config.params.width)
        seed       = await context.render_variable(self.config.seed)

        return {
            "num_frames": num_frames,
            "fps":        fps,
            "height":     height,
            "width":      width,
            "seed":       seed,
        }

    @abstractmethod
    async def _generate_batch(
        self,
        prompts: List[str],
        negative_prompts: Optional[List[Optional[str]]],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
