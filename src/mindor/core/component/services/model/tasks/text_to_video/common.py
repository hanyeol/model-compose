from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import TextToVideoModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class TextToVideoTaskAction(ModelTaskComponentAction):
    def __init__(self, config: TextToVideoModelActionConfig):
        self.config: TextToVideoModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result[]", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, bool, bool]:
        """Render the action's inputs into a batched tuple plus `(is_single, is_streaming)` flags.

        Default is "prompt only"; override to append `negative_prompt`, a
        reference `image`, control inputs, etc. The order chosen here is the
        order `_build_pipeline_input_params` (or the subclass's generate loop)
        consumes.
        """
        prompt = await context.render_text(self.config.prompt)

        is_single_input    = not isinstance(prompt, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(prompt, (StreamIterator, AsyncIterator))

        return (prompt,), is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_frames = await context.render_scalar(self.config.params.num_frames, int)
        frame_rate = await context.render_scalar(self.config.params.frame_rate, float)
        height     = await context.render_scalar(self.config.params.height, int)
        width      = await context.render_scalar(self.config.params.width, int)
        seed       = await context.render_scalar(self.config.seed, int)

        return {
            "num_frames": num_frames,
            "frame_rate": frame_rate,
            "height":     height,
            "width":      width,
            "seed":       seed,
        }

    @abstractmethod
    async def _generate_batch(
        self,
        inputs: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[VideoStreamResource]:
        pass
