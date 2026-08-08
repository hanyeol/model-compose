from __future__ import annotations

from typing import Optional, Union, Dict, List, Any
import sys
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageProcessorActionConfig, ImageProcessorActionMethod, ImageScaleMode, FlipDirection, ImageConcatMode, ImageOverlayAnchor, ImageCompressStrategy
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.image import ImageArrayValue
from mindor.core.logger import logging
from ..base import ComponentActionContext
from ....action.base import ComponentAction
from PIL import Image as PILImage
import asyncio

class ImageProcessorAction(ComponentAction):
    def __init__(self, config: ImageProcessorActionConfig):
        self.config: ImageProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await self._prepare_input(self.config.method, context)
        batch_size = await context.render_variable(self.config.batch_size)

        params = await self._resolve_params(self.config.method, context)

        is_single_input  = not isinstance(image, (list, StreamIterator, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, (StreamIterator, AsyncIterator)):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(self.config.method, batch_images, params)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._process_batch(self.config.method, batch_images, params)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _prepare_input(self, method: ImageProcessorActionMethod, context: ComponentActionContext) -> Any:
        if method in (ImageProcessorActionMethod.CONCAT, ImageProcessorActionMethod.MERGE):
            return await context.render_image_array(self.config.image)

        return await context.render_image(self.config.image)

    async def _resolve_params(self, method: ImageProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == ImageProcessorActionMethod.RESIZE:
            width      = await context.render_scalar(self.config.width, int)
            height     = await context.render_scalar(self.config.height, int)
            scale_mode = await context.render_variable(self.config.scale_mode)

            if width is None and height is None:
                raise ValueError("At least one of 'width' or 'height' must be specified for 'resize' method")

            try:
                scale_mode = ImageScaleMode(scale_mode)
            except ValueError:
                raise ValueError(f"Invalid scale_mode: {scale_mode}")

            return { "width": width, "height": height, "scale_mode": scale_mode }

        if method == ImageProcessorActionMethod.CROP:
            x      = await context.render_scalar(self.config.x, int)
            y      = await context.render_scalar(self.config.y, int)
            width  = await context.render_scalar(self.config.width, int)
            height = await context.render_scalar(self.config.height, int)

            if x is None or y is None or width is None or height is None:
                raise ValueError("'x', 'y', 'width', and 'height' must all be specified for 'crop' method")

            return { "x": x, "y": y, "width": width, "height": height }

        if method == ImageProcessorActionMethod.ROTATE:
            angle  = await context.render_scalar(self.config.angle, float)
            expand = await context.render_scalar(self.config.expand, bool)

            if angle is None:
                raise ValueError("'angle' must be specified for 'rotate' method")

            return { "angle": angle, "expand": expand }

        if method == ImageProcessorActionMethod.FLIP:
            direction = await context.render_variable(self.config.direction)

            if direction is None:
                raise ValueError("'direction' must be specified for 'flip' method")

            try:
                direction = FlipDirection(direction)
            except ValueError:
                raise ValueError(f"Invalid flip direction: {direction}")

            return { "direction": direction }

        if method == ImageProcessorActionMethod.GRAYSCALE:
            return {}

        if method == ImageProcessorActionMethod.BLUR:
            radius = await context.render_scalar(self.config.radius, float)

            if radius is None:
                raise ValueError("'radius' must be specified for 'blur' method")

            return { "radius": radius }

        if method == ImageProcessorActionMethod.SHARPEN:
            factor = await context.render_scalar(self.config.factor, float)

            if factor is None:
                raise ValueError("'factor' must be specified for 'sharpen' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_BRIGHTNESS:
            factor = await context.render_scalar(self.config.factor, float)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-brightness' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_CONTRAST:
            factor = await context.render_scalar(self.config.factor, float)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-contrast' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_SATURATION:
            factor = await context.render_scalar(self.config.factor, float)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-saturation' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.CONCAT:
            mode       = await context.render_variable(self.config.mode)
            columns    = await context.render_scalar(self.config.columns, int)
            rows       = await context.render_scalar(self.config.rows, int)
            spacing    = await context.render_scalar(self.config.spacing, int)
            background = await context.render_color(self.config.background)

            try:
                mode = ImageConcatMode(mode)
            except ValueError:
                raise ValueError(f"Invalid concat mode: {mode}")

            return {
                "mode":       mode,
                "columns":    columns,
                "rows":       rows,
                "spacing":    spacing or 0,
                "background": background,
            }

        if method == ImageProcessorActionMethod.MERGE:
            background = await context.render_color(self.config.background)

            return {
                "background": background,
            }

        if method == ImageProcessorActionMethod.OVERLAY:
            overlay = await context.render_image(self.config.overlay)
            x       = await context.render_scalar(self.config.x, int)
            y       = await context.render_scalar(self.config.y, int)
            width   = await context.render_scalar(self.config.width, int)
            height  = await context.render_scalar(self.config.height, int)
            anchor  = await context.render_variable(self.config.anchor)
            opacity = await context.render_scalar(self.config.opacity, float)

            if isinstance(overlay, (list, StreamIterator, AsyncIterator)):
                raise ValueError("'overlay' must resolve to a single image, not a batch or stream")

            if x is None or y is None:
                raise ValueError("'x' and 'y' must be specified for 'overlay' method")

            try:
                anchor = ImageOverlayAnchor(anchor)
            except ValueError:
                raise ValueError(f"Invalid overlay anchor: {anchor}")

            if not 0.0 <= opacity <= 1.0:
                raise ValueError(f"'opacity' must be between 0.0 and 1.0, got {opacity}")

            return {
                "overlay": overlay,
                "x":       x,
                "y":       y,
                "width":   width,
                "height":  height,
                "anchor":  anchor,
                "opacity": opacity,
            }

        if method == ImageProcessorActionMethod.COMPRESS:
            strategy       = await context.render_variable(self.config.strategy)
            compress_level = await context.render_scalar(self.config.compress_level, int)
            min_quality    = await context.render_scalar(self.config.min_quality, int)
            max_quality    = await context.render_scalar(self.config.max_quality, int)
            speed          = await context.render_scalar(self.config.speed, int)
            level          = await context.render_scalar(self.config.level, int)
            strip_metadata = await context.render_scalar(self.config.strip_metadata, bool)

            try:
                strategy = ImageCompressStrategy(strategy)
            except ValueError:
                raise ValueError(f"Invalid compress strategy: {strategy}")

            return {
                "strategy":       strategy,
                "compress_level": compress_level,
                "min_quality":    min_quality,
                "max_quality":    max_quality,
                "speed":          speed,
                "level":          level,
                "strip_metadata": strip_metadata,
            }

        raise ValueError(f"Unsupported image processing action method: {self.config.method}")

    async def _process_batch(
        self,
        method: ImageProcessorActionMethod,
        images: Union[List[PILImage.Image], List[ImageArrayValue]],
        params: Dict[str, Any],
    ) -> List[Optional[PILImage.Image]]:
        return await asyncio.gather(*[
            self._process(method, image, params) for image in images
        ])

    async def _process(self, method: ImageProcessorActionMethod, image: Union[PILImage.Image, ImageArrayValue], params: Dict[str, Any]) -> Optional[PILImage.Image]:
        if image is None:
            logging.debug("Image processor (%s) skipped because no image was provided.", method)
            return None

        if method == ImageProcessorActionMethod.RESIZE:
            return await self._resize(image, params)

        if method == ImageProcessorActionMethod.CROP:
            return await self._crop(image, params)

        if method == ImageProcessorActionMethod.ROTATE:
            return await self._rotate(image, params)

        if method == ImageProcessorActionMethod.FLIP:
            return await self._flip(image, params)

        if method == ImageProcessorActionMethod.GRAYSCALE:
            return await self._grayscale(image, params)

        if method == ImageProcessorActionMethod.BLUR:
            return await self._blur(image, params)

        if method == ImageProcessorActionMethod.SHARPEN:
            return await self._sharpen(image, params)

        if method == ImageProcessorActionMethod.ADJUST_BRIGHTNESS:
            return await self._adjust_brightness(image, params)

        if method == ImageProcessorActionMethod.ADJUST_CONTRAST:
            return await self._adjust_contrast(image, params)

        if method == ImageProcessorActionMethod.ADJUST_SATURATION:
            return await self._adjust_saturation(image, params)

        if method == ImageProcessorActionMethod.CONCAT:
            return await self._concat(await image.collect(), params)

        if method == ImageProcessorActionMethod.MERGE:
            return await self._merge(await image.collect(), params)

        if method == ImageProcessorActionMethod.OVERLAY:
            return await self._overlay(image, params)

        if method == ImageProcessorActionMethod.COMPRESS:
            return await self._compress(image, params)

        raise ValueError(f"Unsupported image processing action method: {method}")

    @abstractmethod
    async def _resize(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _crop(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _rotate(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _flip(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _grayscale(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _blur(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _sharpen(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _adjust_brightness(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _adjust_contrast(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _adjust_saturation(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _concat(self, images: List[PILImage.Image], params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _merge(self, images: List[PILImage.Image], params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _overlay(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        pass
