from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import ImageProcessorActionConfig, ImageScaleMode, FlipDirection, ImageMergeMode
from ..base import ImageProcessorService, ImageProcessorDriver, register_image_processor_service
from ..base import ComponentActionContext
from .common import ImageProcessorAction
from PIL import Image as PILImage, ImageFilter, ImageEnhance
import asyncio, math

class NativeImageProcessorAction(ImageProcessorAction):
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

    def _merge(self, images: List[PILImage.Image], params: Dict[str, Any]) -> PILImage.Image:
        mode       = params["mode"]
        spacing    = params["spacing"]
        background = params["background"]
        images     = [ image.convert("RGBA") for image in images ]

        if mode == ImageMergeMode.HORIZONTAL:
            return self._merge_horizontal(images, spacing, background)

        if mode == ImageMergeMode.VERTICAL:
            return self._merge_vertical(images, spacing, background)

        if mode == ImageMergeMode.GRID:
            return self._merge_grid(images, params["columns"], params["rows"], spacing, background)

        if mode == ImageMergeMode.OVERLAY:
            return self._merge_overlay(images, background)

        raise ValueError(f"Unsupported merge mode: {mode}")

    def _merge_horizontal(self, images: List[PILImage.Image], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
        total_width = sum(image.width for image in images) + spacing * (len(images) - 1)
        max_height  = max(image.height for image in images)
        canvas      = PILImage.new("RGBA", (total_width, max_height), background)

        offset_x = 0
        for image in images:
            offset_y = (max_height - image.height) // 2
            canvas.paste(image, (offset_x, offset_y), image)
            offset_x += image.width + spacing

        return canvas

    def _merge_vertical(self, images: List[PILImage.Image], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
        max_width    = max(image.width for image in images)
        total_height = sum(image.height for image in images) + spacing * (len(images) - 1)
        canvas       = PILImage.new("RGBA", (max_width, total_height), background)

        offset_y = 0
        for image in images:
            offset_x = (max_width - image.width) // 2
            canvas.paste(image, (offset_x, offset_y), image)
            offset_y += image.height + spacing

        return canvas

    def _merge_grid(self, images: List[PILImage.Image], columns: Optional[int], rows: Optional[int], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
        count = len(images)

        if columns and rows:
            grid_columns, grid_rows = columns, rows
        elif columns:
            grid_columns = columns
            grid_rows    = (count + columns - 1) // columns
        elif rows:
            grid_rows    = rows
            grid_columns = (count + rows - 1) // rows
        else:
            grid_columns = math.ceil(math.sqrt(count))
            grid_rows    = (count + grid_columns - 1) // grid_columns

        cell_width  = max(image.width for image in images)
        cell_height = max(image.height for image in images)
        total_width  = cell_width  * grid_columns + spacing * (grid_columns - 1)
        total_height = cell_height * grid_rows    + spacing * (grid_rows    - 1)
        canvas = PILImage.new("RGBA", (total_width, total_height), background)

        for index, image in enumerate(images):
            if index >= grid_columns * grid_rows:
                break

            column   = index %  grid_columns
            row      = index // grid_columns
            offset_x = column * (cell_width  + spacing) + (cell_width  - image.width ) // 2
            offset_y = row    * (cell_height + spacing) + (cell_height - image.height) // 2
            canvas.paste(image, (offset_x, offset_y), image)

        return canvas

    def _merge_overlay(self, images: List[PILImage.Image], background: Tuple[int, int, int, int]) -> PILImage.Image:
        max_width  = max(image.width  for image in images)
        max_height = max(image.height for image in images)
        canvas     = PILImage.new("RGBA", (max_width, max_height), background)

        for image in images:
            offset_x = (max_width  - image.width ) // 2
            offset_y = (max_height - image.height) // 2
            canvas.alpha_composite(image, (offset_x, offset_y))

        return canvas

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

@register_image_processor_service(ImageProcessorDriver.NATIVE)
class NativeImageProcessorService(ImageProcessorService):
    def __init__(self, id: str, config: ImageProcessorComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        return await NativeImageProcessorAction(action).run(context, loop)
