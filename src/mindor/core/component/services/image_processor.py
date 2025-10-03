from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import ActionConfig, ImageProcessorActionConfig, ImageProcessorActionMethod, ImageScaleMode, FlipDirection
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
from PIL import Image as PILImage, ImageFilter, ImageEnhance

class ImageProcessorAction:
    def __init__(self, config: ImageProcessorActionConfig):
        self.config: ImageProcessorActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        result = await self._dispatch(context)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext) -> Any:
        if self.config.method == ImageProcessorActionMethod.RESIZE:
            return await self._resize(context)

        if self.config.method == ImageProcessorActionMethod.CROP:
            return await self._crop(context)

        if self.config.method == ImageProcessorActionMethod.ROTATE:
            return await self._rotate(context)

        if self.config.method == ImageProcessorActionMethod.FLIP:
            return await self._flip(context)

        if self.config.method == ImageProcessorActionMethod.GRAYSCALE:
            return await self._grayscale(context)

        if self.config.method == ImageProcessorActionMethod.BLUR:
            return await self._blur(context)

        if self.config.method == ImageProcessorActionMethod.SHARPEN:
            return await self._sharpen(context)

        if self.config.method == ImageProcessorActionMethod.ADJUST_BRIGHTNESS:
            return await self._adjust_brightness(context)

        if self.config.method == ImageProcessorActionMethod.ADJUST_CONTRAST:
            return await self._adjust_contrast(context)

        if self.config.method == ImageProcessorActionMethod.ADJUST_SATURATION:
            return await self._adjust_saturation(context)

        raise ValueError(f"Unsupported image processing action method: {self.config.method}")

    async def _resize(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image      = await context.render_image(self.config.image)
        width      = await context.render_variable(self.config.width) if self.config.width else None
        height     = await context.render_variable(self.config.height) if self.config.height else None
        scale_mode = await context.render_variable(self.config.scale_mode)

        if width is None and height is None:
            raise ValueError("At least one of width or height must be specified for resize")

        if image:
            return self._resize_image(image, width, height, scale_mode)
        
        return None

    async def _crop(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        x      = await context.render_variable(self.config.x)
        y      = await context.render_variable(self.config.y)
        width  = await context.render_variable(self.config.width)
        height = await context.render_variable(self.config.height)

        if image:
            return image.crop(x, y, x + width, y + height)
        
        return None

    async def _rotate(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        angle  = await context.render_variable(self.config.angle)
        expand = await context.render_variable(self.config.expand)

        if image:
            return image.rotate(-angle, expand=expand, resample=PILImage.Resampling.BICUBIC)

        return None

    async def _flip(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image     = await context.render_image(self.config.image)
        direction = await context.render_variable(self.config.direction)

        if image:
            if direction == FlipDirection.HORIZONTAL:
                return image.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)

            if direction == FlipDirection.VERTICAL:
                return image.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)

        return None

    async def _grayscale(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image = await context.render_image(self.config.image)

        if image:
            return image.convert("L")

        return None

    async def _blur(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        radius = await context.render_variable(self.config.radius)

        if image:
            return image.filter(ImageFilter.GaussianBlur(radius=radius))

    async def _sharpen(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        factor = await context.render_variable(self.config.factor)

        if image:
            return ImageEnhance.Sharpness(image).enhance(factor)

        return FileNotFoundError

    async def _adjust_brightness(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        factor = await context.render_variable(self.config.factor)

        if image:
            return ImageEnhance.Brightness(image).enhance(factor)

        return None

    async def _adjust_contrast(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        factor = await context.render_variable(self.config.factor)

        if image:
            return ImageEnhance.Contrast(image).enhance(factor)

        return image

    async def _adjust_saturation(self, context: ComponentActionContext) -> Optional[PILImage.Image]:
        image  = await context.render_image(self.config.image)
        factor = await context.render_variable(self.config.factor)

        if image:
            return ImageEnhance.Color(image).enhance(factor)

        return None

    def _resize_image(self, image: PILImage.Image, width: int, height: int, scale_mode: str) -> PILImage.Image:
        original_width, original_height = image.size
        target_width  = width  or original_width
        target_height = height or original_height

        if scale_mode == ImageScaleMode.FIT:
            new_width, new_height = self._get_size_aspect_fit(target_width, target_height, original_width, original_height)
            return image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

        if scale_mode == ImageScaleMode.FILL:
            new_width, new_height = self._get_size_aspect_fill(target_width, target_height, original_width, original_height)
            image = image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

            crop_box = self._get_center_crop_box(new_width, new_height, target_width, target_height)
            return image.crop(crop_box)

        if scale_mode == ImageScaleMode.STRETCH:
            return image.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

        raise ValueError(f"Invalid scale_mode: {scale_mode}")

    def _get_size_aspect_fit(self, target_width: int, target_height: int, original_width: int, original_height: int) -> Tuple[int, int]:
        aspect_ratio = original_width / original_height

        height = target_height
        width  = height * aspect_ratio

        if width > target_width:
            width  = target_width
            height = width / aspect_ratio

        return (int(width), int(height))

    def _get_size_aspect_fill(self, target_width: int, target_height: int, original_width: int, original_height: int) -> Tuple[int, int]:
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
    def __init__(self, id: str, config: ImageProcessorComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await ImageProcessorAction(action).run(context)
