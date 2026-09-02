from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import VideoEmbeddingModelActionConfig
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.atomic import AtomicList
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext

class VideoEmbedding(AtomicList):
    def __log__(self) -> str:
        return f"<VideoEmbedding dim={len(self)}>"

class VideoEmbeddingTaskAction(ComponentAction):
    def __init__(self, config: VideoEmbeddingModelActionConfig):
        self.config: VideoEmbeddingModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        frames     = await context.render_image_array(self.config.frames, single_as_array=True)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = isinstance(frames, ImageArrayValue) and frames.is_single
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(frames, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_videos in BatchSourceIterator(frames, batch_size=batch_size or 1):
                    batch_results = await self._embed_batch(batch_videos, params, context.cancellation_token)
                    for result in batch_results:
                        yield VideoEmbedding(result)

            return _stream_output_generator()
        else:
            results: List[VideoEmbedding] = []
            async for batch_videos in BatchSourceIterator(frames, batch_size=batch_size or 1):
                batch_results = await self._embed_batch(batch_videos, params, context.cancellation_token)
                results.extend(VideoEmbedding(result) for result in batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        normalize = await context.render_scalar(self.config.params.normalize, bool)

        return {
            "normalize": normalize,
        }

    @abstractmethod
    async def _embed_batch(
        self,
        videos: List[ImageArrayValue],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[float]]:
        pass
