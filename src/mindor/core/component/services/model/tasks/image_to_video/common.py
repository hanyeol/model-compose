from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageToVideoModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.video import VideoStreamResource
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction

class ImageToVideoTaskAction(ModelTaskComponentAction):
    def __init__(self, config: ImageToVideoModelActionConfig):
        self.config: ImageToVideoModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        input, primary_input, is_single_input, is_streaming_input = await self._prepare_input(context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_direct_output = not self.config.output or self.config.output == "${result}"

        if is_streaming_input:
            async def _stream_output_generator():
                async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                    batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                    for result in batch_results:
                        context.register_source("result", result)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else result

            if isinstance(primary_input, StreamChunkIterator) and primary_input.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[VideoStreamResource] = []
            async for batch_inputs in BatchSourceIterator(input, batch_size=batch_size or 1):
                batch_results = await self._generate_batch(batch_inputs, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, context: ComponentActionContext) -> Tuple[Any, Any, bool, bool]:
        image  = await context.render_image(self.config.image)
        prompt = await context.render_text(self.config.prompt) if self.config.prompt is not None else None

        is_single_input    = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_streaming_input = isinstance(image, (StreamIterator, AsyncIterator))

        return (image, prompt), image, is_single_input, is_streaming_input

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        num_frames = await context.render_variable(self.config.params.num_frames)
        width      = await context.render_variable(self.config.width)
        height     = await context.render_variable(self.config.height)
        frame_rate = await context.render_scalar(self.config.frame_rate, float)
        seed       = await context.render_variable(self.config.seed)

        return {
            "num_frames": num_frames,
            "width":      width,
            "height":     height,
            "frame_rate": frame_rate,
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
