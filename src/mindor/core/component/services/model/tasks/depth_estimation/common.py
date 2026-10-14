from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import DepthEstimationModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamChunkIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from ...base import ComponentActionContext, ModelTaskComponentAction
from PIL import Image as PILImage

if TYPE_CHECKING:
    import torch

class DepthEstimationTaskAction(ModelTaskComponentAction):
    def __init__(self, config: DepthEstimationModelActionConfig, device: Optional[torch.device]):
        self.config: DepthEstimationModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_depths = await self._estimate_batch(batch_images, params, context.cancellation_token)
                    for depth in batch_depths:
                        context.register_source("result", depth)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else depth

            if isinstance(image, StreamChunkIterator) and image.is_fragmented:
                return StreamChunkIterator(_stream_output_generator(), is_fragmented=True)

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_depths = await self._estimate_batch(batch_images, params, context.cancellation_token)
                results.extend(batch_depths)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        invert = await context.render_variable(self.config.invert)

        return {
            "invert": bool(invert),
        }

    @abstractmethod
    async def _estimate_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[PILImage.Image]:
        pass
