from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import FaceSwapModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class FaceSwapTaskAction:
    def __init__(self, config: FaceSwapModelActionConfig):
        self.config: FaceSwapModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        source_image = await context.render_image(self.config.source_image)
        target_image = await context.render_image(self.config.target_image)
        batch_size   = await context.render_variable(self.config.batch_size)

        if isinstance(source_image, (list, StreamIterator, AsyncIterator)):
            raise ValueError("'source_image' must be a single image, not a batch or stream.")

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(target_image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        source_face = self._prepare_source_face(source_image, params, context.cancellation_token)

        if isinstance(target_image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(target_image, batch_size=batch_size or 1):
                    batch_results = self._swap(batch_images, source_face, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[PILImage.Image] = []
            async for batch_images in BatchSourceIterator(target_image, batch_size=batch_size or 1):
                batch_results = self._swap(batch_images, source_face, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        swap_all_faces = await context.render_variable(self.config.swap_all_faces)
        face_index     = await context.render_variable(self.config.face_index)

        if int(face_index) < 0:
            raise ValueError(f"'face_index' must be >= 0, got {int(face_index)}")

        return {
            "swap_all_faces": bool(swap_all_faces),
            "face_index":     int(face_index),
        }

    @abstractmethod
    def _prepare_source_face(
        self,
        image: PILImage.Image,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> Any:
        pass

    @abstractmethod
    def _swap(
        self,
        images: List[PILImage.Image],
        source_face: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[PILImage.Image]:
        pass

class FaceSwapTaskService(ModelTaskService):
    pass
