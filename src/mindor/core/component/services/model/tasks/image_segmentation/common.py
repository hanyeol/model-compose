from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageSegmentationModelActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from .....action.base import ComponentAction
from ...base import ComponentActionContext
from PIL import Image as PILImage

class ImageSegmentationTaskAction(ComponentAction):
    def __init__(self, config: ImageSegmentationModelActionConfig):
        self.config: ImageSegmentationModelActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._segment_batch(batch_images, params, context.cancellation_token)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results: List[Dict[str, Any]] = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._segment_batch(batch_images, params, context.cancellation_token)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        box_prompt        = await context.render_variable(self.config.box_prompt)
        max_segment_count = await context.render_scalar(self.config.max_segment_count, int)
        return_mask       = await context.render_scalar(self.config.return_mask, bool)
        min_confidence    = await context.render_scalar(self.config.params.min_confidence, float)
        min_area          = await context.render_scalar(self.config.params.min_area, int)

        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError(f"'min_confidence' must be between 0.0 and 1.0, got {min_confidence}")

        if max_segment_count < 1:
            raise ValueError(f"'max_segment_count' must be >= 1, got {max_segment_count}")

        if min_area is not None and min_area < 0:
            raise ValueError(f"'min_area' must be >= 0, got {min_area}")

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
            "min_confidence":    min_confidence,
            "min_area":          min_area,
            "max_segment_count": max_segment_count,
            "return_mask":       return_mask,
        }

    @abstractmethod
    async def _segment_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
