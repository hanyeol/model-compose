from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ObjectDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class ObjectDetectionTaskAction(ComponentAction):
    def __init__(self, config: ObjectDetectionModelActionConfig):
        self.config: ObjectDetectionModelActionConfig = config

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
        labels               = await context.render_variable(self.config.labels)
        min_confidence       = await context.render_scalar(self.config.min_confidence, float)
        max_object_count     = await context.render_scalar(self.config.max_object_count, int)
        iou_threshold        = await context.render_scalar(self.config.iou_threshold, float)
        agnostic_nms         = await context.render_scalar(self.config.agnostic_nms, bool)
        bounding_box_padding = await context.render_scalar(self.config.bounding_box_padding, float)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        if not 0.0 <= iou_threshold <= 1.0:
            raise ValueError(f"'iou_threshold' must be between 0.0 and 1.0, got {iou_threshold}")

        if max_object_count < 1:
            raise ValueError(f"'max_object_count' must be >= 1, got {max_object_count}")

        if bounding_box_padding < 0.0:
            raise ValueError(f"'bounding_box_padding' must be >= 0.0, got {bounding_box_padding}")

        if labels is not None and not isinstance(labels, list):
            labels = [ labels ]

        return {
            "labels":               [ str(label) for label in labels ] if labels else None,
            "min_confidence":       min_confidence,
            "max_object_count":     max_object_count,
            "iou_threshold":        iou_threshold,
            "agnostic_nms":         agnostic_nms,
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
