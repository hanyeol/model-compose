from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageSegmentationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from ...base import ModelTaskService, ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ImageSegmentationTaskAction:
    def __init__(self, config: ImageSegmentationModelActionConfig):
        self.config: ImageSegmentationModelActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = self._segment(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = self._segment(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        box_prompt        = await context.render_variable(self.config.box_prompt)
        min_confidence    = await context.render_variable(self.config.min_confidence)
        min_area          = await context.render_variable(self.config.min_area) if self.config.min_area is not None else None
        max_segment_count = await context.render_variable(self.config.max_segment_count)
        return_mask       = await context.render_variable(self.config.return_mask)

        if not 0.0 <= float(min_confidence) <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {float(min_confidence)}")

        if int(max_segment_count) < 1:
            raise ValueError(f"'max_segment_count' must be >= 1, got {int(max_segment_count)}")

        if min_area is not None and int(min_area) < 0:
            raise ValueError(f"'min_area' must be >= 0, got {int(min_area)}")

        box_prompts: Optional[List[List[Union[int, float]]]] = None

        if box_prompt is not None:
            if not isinstance(box_prompt, list):
                raise ValueError(f"'box_prompt' must be a list, got {type(box_prompt).__name__}")

            box_prompts = box_prompt if box_prompt and isinstance(box_prompt[0], (list, tuple)) else [ box_prompt ]

            for index, box in enumerate(box_prompts):
                if not isinstance(box, (list, tuple)) or len(box) != 4:
                    raise ValueError(f"'box_prompt[{index}]' must be a 4-element list [x, y, width, height], got {box!r}")

        return {
            "box_prompts":       box_prompts,
            "min_confidence":    float(min_confidence),
            "min_area":          int(min_area) if min_area is not None else None,
            "max_segment_count": int(max_segment_count),
            "return_mask":       bool(return_mask),
        }

    @abstractmethod
    def _segment(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None
    ) -> List[Dict[str, Any]]:
        pass

class ImageSegmentationTaskService(ModelTaskService):
    pass
