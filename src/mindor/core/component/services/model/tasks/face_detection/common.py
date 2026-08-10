from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import FaceDetectionModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class FaceDetectionTaskAction(ComponentAction):
    def __init__(self, config: FaceDetectionModelActionConfig):
        self.config: FaceDetectionModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._detect_batch(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._detect_batch(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        min_confidence       = await context.render_scalar(self.config.params.min_confidence, float)
        return_landmarks     = await context.render_scalar(self.config.return_landmarks, bool)
        bounding_box_padding = await context.render_scalar(self.config.bounding_box_padding, float)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        if bounding_box_padding < 0.0:
            raise ValueError(f"'bounding_box_padding' must be >= 0.0, got {bounding_box_padding}")

        return {
            "min_confidence":       min_confidence,
            "return_landmarks":     return_landmarks,
            "bounding_box_padding": bounding_box_padding,
        }

    @abstractmethod
    async def _detect_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
