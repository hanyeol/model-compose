from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import ActionConfig, ImageProcessorActionConfig, ImageProcessorActionMethod, ImageScaleMode, FlipDirection
from mindor.core.utils.iterator import AsyncSourceIterator
from mindor.core.logger import logging
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from PIL import Image as PILImage, ImageFilter, ImageEnhance
import asyncio

class ImageProcessorAction:
    def __init__(self, config: ImageProcessorActionConfig):
        self.config: ImageProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
        batch_size = await context.render_variable(self.config.batch_size)

        is_stream_input  = isinstance(image, AsyncIterator)
        is_stream_output = context.contains_variable_reference("result[]", self.config.output)
        is_direct_output = not self.config.output or self.config.output == "${result}"
        is_stream_mode   = is_stream_output or (is_stream_input and is_direct_output)

        if is_stream_mode:
            async def _stream_output_generator():
                async for batch_images in AsyncSourceIterator(image, batch_size=batch_size or 1):
                    processed_images = await self._process_batch(batch_images, context)
                    for processed_image in processed_images:
                        context.register_source("result[]", processed_image)
                        yield (await context.render_variable(self.config.output)) if not is_direct_output else processed_image

            return _stream_output_generator()

        is_single_input: bool = not isinstance(image, (list, AsyncIterator))
        results = []
        async for batch_images in AsyncSourceIterator(image, batch_size=batch_size or 1):
            processed_images = await self._process_batch(batch_images, context)
            results.extend(processed_images)

        result = results[0] if is_single_input else results
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if not is_direct_output else result

    async def _process_batch(self, images: List[PILImage.Image], context: ComponentActionContext) -> Any:
        method = await context.render_variable(self.config.method)

        if method is None:
            raise ValueError("'method' must be specified for image processor")

        try:
            method = ImageProcessorActionMethod(method)
        except ValueError:
            raise ValueError(f"Unsupported image processing action method: {method}")

        params = await self._render_params(method, context)

        return await asyncio.gather(*[
            asyncio.to_thread(self._process, image, method, params) for image in images
        ])

    async def _render_params(self, method: ImageProcessorActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
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

    def _process(self, image: PILImage.Image, method: ImageProcessorActionMethod, params: Dict[str, Any]) -> Optional[PILImage.Image]:
        if image is None:
            logging.debug("[image-processor] received None image for '%s' method, skipping", method)
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

    def _resize(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        scale_mode = params["scale_mode"]
        original_width, original_height = image.size
        target_width  = params["width"]  or original_width
        target_height = params["height"] or original_height

        if scale_mode == ImageScaleMode.FIT:
            new_width, new_height = self._get_size_aspect_fit(target_width, target_height, original_width, original_height)
            return image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

        if scale_mode == ImageScaleMode.FILL:
            new_width, new_height = self._get_size_aspect_fill(target_width, target_height, original_width, original_height)
            image = image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

            crop_box = self._get_center_crop_box(new_width, new_height, target_width, target_height)
            return image.crop(crop_box)

        return image.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

    def _crop(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        x      = params["x"]
        y      = params["y"]
        width  = params["width"]
        height = params["height"]

        return image.crop((x, y, x + width, y + height))

    def _rotate(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return image.rotate(-params["angle"], expand=params["expand"], resample=PILImage.Resampling.BICUBIC)

    def _flip(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        if params["direction"] == FlipDirection.HORIZONTAL:
            return image.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
        else:
            return image.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)

    def _grayscale(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return image.convert("L")

    def _blur(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return image.filter(ImageFilter.GaussianBlur(radius=params["radius"]))

    def _sharpen(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return ImageEnhance.Sharpness(image).enhance(params["factor"])

    def _adjust_brightness(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return ImageEnhance.Brightness(image).enhance(params["factor"])

    def _adjust_contrast(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return ImageEnhance.Contrast(image).enhance(params["factor"])

    def _adjust_saturation(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        return ImageEnhance.Color(image).enhance(params["factor"])

    def _get_size_aspect_fit(
        self,
        target_width: int,
        target_height: int,
        original_width: int,
        original_height: int
    ) -> Tuple[int, int]:
        aspect_ratio = original_width / original_height

        height = target_height
        width  = height * aspect_ratio

        if width > target_width:
            width  = target_width
            height = width / aspect_ratio

        return (int(width), int(height))

    def _get_size_aspect_fill(
        self,
        target_width: int,
        target_height: int,
        original_width: int,
        original_height: int
    ) -> Tuple[int, int]:
        aspect_ratio = original_width / original_height

        height = target_height
        width  = height * aspect_ratio

        if width < target_width:
            width  = target_width
            height = width / aspect_ratio

        return (int(width), int(height))

    def _get_center_crop_box(self, image_width: int, image_height: int, target_width: int, target_height: int) -> Tuple[int, int, int, int]:
        left   = (image_width  - target_width ) // 2
        top    = (image_height - target_height) // 2
        right  = left + target_width
        bottom = top + target_height

        return (left, top, right, bottom)

@register_component(ComponentType.IMAGE_PROCESSOR)
class ImageProcessorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ImageProcessorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ImageProcessorAction(action).run(context)
