from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ObjectDetectionModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ObjectDetectionTaskAction:
    def __init__(self, config: ObjectDetectionModelActionConfig):
        self.config: ObjectDetectionModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = self._detect(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = self._detect(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        labels               = await context.render_variable(self.config.labels)
        min_confidence       = await context.render_variable(self.config.min_confidence)
        max_object_count     = await context.render_variable(self.config.max_object_count)
        iou_threshold        = await context.render_variable(self.config.iou_threshold)
        agnostic_nms         = await context.render_variable(self.config.agnostic_nms)
        bounding_box_padding = await context.render_variable(self.config.bounding_box_padding)

        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {float(min_confidence)}")

        if not 0.0 <= float(iou_threshold) <= 1.0:
            raise ValueError(f"'iou_threshold' must be between 0.0 and 1.0, got {float(iou_threshold)}")

        if int(max_object_count) < 1:
            raise ValueError(f"'max_object_count' must be >= 1, got {int(max_object_count)}")

        if float(bounding_box_padding) < 0.0:
            raise ValueError(f"'bounding_box_padding' must be >= 0.0, got {float(bounding_box_padding)}")

        if labels is not None and not isinstance(labels, list):
            labels = [ labels ]

        return {
            "labels":               [ str(label) for label in labels ] if labels else None,
            "min_confidence":       float(min_confidence),
            "max_object_count":     int(max_object_count),
            "iou_threshold":        float(iou_threshold),
            "agnostic_nms":         bool(agnostic_nms),
            "bounding_box_padding": float(bounding_box_padding),
        }

    @abstractmethod
    def _detect(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
        pass

class ObjectDetectionTaskService(ModelTaskService):
    pass
