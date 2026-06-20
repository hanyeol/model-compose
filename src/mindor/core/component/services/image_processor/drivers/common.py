from __future__ import annotations

from typing import Optional, Dict, List, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import ImageProcessorActionConfig, ImageProcessorActionMethod, ImageScaleMode, FlipDirection
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import ComponentActionContext
from PIL import Image as PILImage
import asyncio

class ImageProcessorAction:
    def __init__(self, config: ImageProcessorActionConfig):
        self.config: ImageProcessorActionConfig = config

    async def run(self, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)
        method     = self.config.method

        params = await self._resolve_params(method, context)

        is_single_input  = not isinstance(image, (list, AsyncIterator))
        is_direct_output = not self.config.output or self.config.output == "${result}"

        if isinstance(image, AsyncIterator):
            async def _stream_output_generator():
                async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                    batch_results = await self._process_batch(batch_images, method, params, loop)
                    for result in batch_results:
                        yield result

            return _stream_output_generator()
        else:
            results = []
            async for batch_images in BatchSourceIterator(image, batch_size=batch_size or 1):
                batch_results = await self._process_batch(batch_images, method, params, loop)
                results.extend(batch_results)

            result = results[0] if is_single_input else results
            context.register_source("result", result)

            return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _resolve_params(self, method: ImageProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == ImageProcessorActionMethod.RESIZE:
            width      = await context.render_variable(self.config.width) if self.config.width else None
            height     = await context.render_variable(self.config.height) if self.config.height else None
            scale_mode = await context.render_variable(self.config.scale_mode)

            if width is None and height is None:
                raise ValueError("At least one of 'width' or 'height' must be specified for 'resize' method")

            try:
                scale_mode = ImageScaleMode(scale_mode)
            except ValueError:
                raise ValueError(f"Invalid scale_mode: {scale_mode}")

            return { "width": width, "height": height, "scale_mode": scale_mode }

        if method == ImageProcessorActionMethod.CROP:
            x      = await context.render_variable(self.config.x)
            y      = await context.render_variable(self.config.y)
            width  = await context.render_variable(self.config.width)
            height = await context.render_variable(self.config.height)

            if x is None or y is None or width is None or height is None:
                raise ValueError("'x', 'y', 'width', and 'height' must all be specified for 'crop' method")

            return { "x": x, "y": y, "width": width, "height": height }

        if method == ImageProcessorActionMethod.ROTATE:
            angle  = await context.render_variable(self.config.angle)
            expand = await context.render_variable(self.config.expand)

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
            radius = await context.render_variable(self.config.radius)

            if radius is None:
                raise ValueError("'radius' must be specified for 'blur' method")

            return { "radius": radius }

        if method == ImageProcessorActionMethod.SHARPEN:
            factor = await context.render_variable(self.config.factor)

            if factor is None:
                raise ValueError("'factor' must be specified for 'sharpen' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_BRIGHTNESS:
            factor = await context.render_variable(self.config.factor)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-brightness' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_CONTRAST:
            factor = await context.render_variable(self.config.factor)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-contrast' method")

            return { "factor": factor }

        if method == ImageProcessorActionMethod.ADJUST_SATURATION:
            factor = await context.render_variable(self.config.factor)

            if factor is None:
                raise ValueError("'factor' must be specified for 'adjust-saturation' method")

            return { "factor": factor }

        raise ValueError(f"Unsupported image processing action method: {self.config.method}")

    async def _process_batch(
        self,
        images: List[PILImage.Image],
        method: ImageProcessorActionMethod,
        params: Dict[str, Any],
        loop: asyncio.AbstractEventLoop,
    ) -> List[Optional[PILImage.Image]]:
        return await asyncio.gather(*[
            asyncio.to_thread(self._process, image, method, params) for image in images
        ])

    def _process(self, image: PILImage.Image, method: ImageProcessorActionMethod, params: Dict[str, Any]) -> Optional[PILImage.Image]:
        if image is None:
            logging.debug("Image processor (%s) skipped because no image was provided.", method)
            return None

        if method == ImageProcessorActionMethod.RESIZE:
            return self._resize(image, params)

        if method == ImageProcessorActionMethod.CROP:
            return self._crop(image, params)

        if method == ImageProcessorActionMethod.ROTATE:
            return self._rotate(image, params)

        if method == ImageProcessorActionMethod.FLIP:
            return self._flip(image, params)

        if method == ImageProcessorActionMethod.GRAYSCALE:
            return self._grayscale(image, params)

        if method == ImageProcessorActionMethod.BLUR:
            return self._blur(image, params)

        if method == ImageProcessorActionMethod.SHARPEN:
            return self._sharpen(image, params)

        if method == ImageProcessorActionMethod.ADJUST_BRIGHTNESS:
            return self._adjust_brightness(image, params)

        if method == ImageProcessorActionMethod.ADJUST_CONTRAST:
            return self._adjust_contrast(image, params)

        if method == ImageProcessorActionMethod.ADJUST_SATURATION:
            return self._adjust_saturation(image, params)

        raise ValueError(f"Unsupported image processing action method: {method}")

    @abstractmethod
    def _resize(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _crop(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _rotate(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _flip(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _grayscale(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _blur(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _sharpen(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _adjust_brightness(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _adjust_contrast(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    def _adjust_saturation(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass
