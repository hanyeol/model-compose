from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageSegmentationModelActionConfig
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.utils.iterators import BatchSourceIterator
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

        box_prompts = self._normalize_box_prompts(box_prompt) if box_prompt is not None else None

        return {
            "box_prompts":       box_prompts,
            "min_confidence":    min_confidence,
            "min_area":          min_area,
            "max_segment_count": max_segment_count,
            "return_mask":       return_mask,
        }

    @staticmethod
    def _normalize_box_prompts(box_prompt: Union[Dict[str, float], List[Dict[str, float]]]) -> List[Dict[str, int]]:
        """Normalize the `box_prompt` field into a list of `{x, y, width, height}`
        dicts. Accepts a single dict or a list of dicts. Detection outputs like
        `${result.faces[*].bounding_box}` flow in as a list of dicts."""
        items = box_prompt if isinstance(box_prompt, list) else [ box_prompt ]
        prompts: List[Dict[str, int]] = []

        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"'box_prompt[{index}]' must be a dict, got {type(item).__name__}")

            missing = [ key for key in ("x", "y", "width", "height") if key not in item ]

            if missing:
                raise ValueError(f"'box_prompt[{index}]' is missing required keys: {missing}")

            prompts.append({
                "x":      int(item["x"]),
                "y":      int(item["y"]),
                "width":  int(item["width"]),
                "height": int(item["height"]),
            })

        return prompts

    @abstractmethod
    async def _segment_batch(
        self,
        images: List[PILImage.Image],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Dict[str, Any]]:
        pass
