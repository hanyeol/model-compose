from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import FaceEmbeddingModelActionConfig
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.logger import logging
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

if TYPE_CHECKING:
    import torch

class FaceEmbeddingTaskAction:
    def __init__(self, config: FaceEmbeddingModelActionConfig, device: Optional[torch.device]):
        self.config: FaceEmbeddingModelActionConfig = config
        self.device: Optional[torch.device] = device

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = self._embed(batch_images, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = self._embed(batch_images, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        face_detection       = bool(await context.render_variable(self.config.face_detection))
        alignment            = bool(await context.render_variable(self.config.alignment))
        normalize_embeddings = bool(await context.render_variable(self.config.normalize_embeddings))

        return {
            "face_detection":       face_detection,
            "alignment":            alignment,
            "normalize_embeddings": normalize_embeddings,
        }

    @abstractmethod
    def _embed(self, images: List[PILImage.Image], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        pass

class FaceEmbeddingTaskService(ModelTaskService):
    pass
