from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import ImageProcessorActionConfig, ImageScaleMode, FlipDirection, ImageConcatMode, ImagePositionAnchor, MosaicMode, ImageRegion
from ..base import ImageProcessorService, ImageProcessorDriver, register_image_processor_service
from ..base import ComponentActionContext
from .common import ImageProcessorAction
from PIL import Image as PILImage, ImageFilter, ImageEnhance, ImageDraw
import math

class NativeImageProcessorAction(ImageProcessorAction):
    async def _resize(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _resize() -> PILImage.Image:
            scale_mode = params["scale_mode"]
            original_width, original_height = image.size
            target_width  = params["width"]  or original_width
            target_height = params["height"] or original_height

            if scale_mode == ImageScaleMode.FIT:
                new_width, new_height = self._get_size_aspect_fit(target_width, target_height, original_width, original_height)
                return image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

            if scale_mode == ImageScaleMode.FILL:
                new_width, new_height = self._get_size_aspect_fill(target_width, target_height, original_width, original_height)
                resized = image.resize((new_width, new_height), PILImage.Resampling.LANCZOS)

                crop_box = self._get_center_crop_box(new_width, new_height, target_width, target_height)
                return resized.crop(crop_box)

            return image.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

        return await self._run_in_executor(_resize)

    async def _crop(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _crop() -> PILImage.Image:
            x      = params["x"]
            y      = params["y"]
            width  = params["width"]
            height = params["height"]

            return image.crop((x, y, x + width, y + height))

        return await self._run_in_executor(_crop)

    async def _rotate(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _rotate() -> PILImage.Image:
            return image.rotate(-params["angle"], expand=params["expand"], resample=PILImage.Resampling.BICUBIC)

        return await self._run_in_executor(_rotate)

    async def _flip(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _flip() -> PILImage.Image:
            if params["direction"] == FlipDirection.HORIZONTAL:
                return image.transpose(PILImage.Transpose.FLIP_LEFT_RIGHT)
            else:
                return image.transpose(PILImage.Transpose.FLIP_TOP_BOTTOM)

        return await self._run_in_executor(_flip)

    async def _grayscale(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _grayscale() -> PILImage.Image:
            return image.convert("L")

        return await self._run_in_executor(_grayscale)

    async def _blur(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _blur() -> PILImage.Image:
            return image.filter(ImageFilter.GaussianBlur(radius=params["radius"]))

        return await self._run_in_executor(_blur)

    async def _sharpen(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _sharpen() -> PILImage.Image:
            return ImageEnhance.Sharpness(image).enhance(params["factor"])

        return await self._run_in_executor(_sharpen)

    async def _adjust_brightness(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _adjust_brightness() -> PILImage.Image:
            return ImageEnhance.Brightness(image).enhance(params["factor"])

        return await self._run_in_executor(_adjust_brightness)

    async def _adjust_contrast(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _adjust_contrast() -> PILImage.Image:
            return ImageEnhance.Contrast(image).enhance(params["factor"])

        return await self._run_in_executor(_adjust_contrast)

    async def _adjust_saturation(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _adjust_saturation() -> PILImage.Image:
            return ImageEnhance.Color(image).enhance(params["factor"])

        return await self._run_in_executor(_adjust_saturation)

    async def _concat(self, images: List[PILImage.Image], params: Dict[str, Any]) -> PILImage.Image:
        def _concat() -> PILImage.Image:
            mode       = params["mode"]
            spacing    = params["spacing"]
            background = params["background"]
            converted  = [ image.convert("RGBA") for image in images ]

            if mode == ImageConcatMode.HORIZONTAL:
                return self._concat_horizontal(converted, spacing, background)

            if mode == ImageConcatMode.VERTICAL:
                return self._concat_vertical(converted, spacing, background)

            if mode == ImageConcatMode.GRID:
                return self._concat_grid(converted, params["columns"], params["rows"], spacing, background)

            raise ValueError(f"Unsupported concat mode: {mode}")

        return await self._run_in_executor(_concat)

    async def _merge(self, images: List[PILImage.Image], params: Dict[str, Any]) -> PILImage.Image:
        def _merge() -> PILImage.Image:
            anchor     = params["anchor"]
            background = params["background"]
            converted  = [ image.convert("RGBA") for image in images ]

            max_width  = max(image.width  for image in converted)
            max_height = max(image.height for image in converted)
            canvas     = PILImage.new("RGBA", (max_width, max_height), background)

            anchor_x, anchor_y = self._resolve_anchor_point(anchor, canvas.size)

            for image in converted:
                offset_x, offset_y = self._resolve_anchor_offset(anchor, anchor_x, anchor_y, image.size)
                canvas.alpha_composite(image, (offset_x, offset_y))

            return canvas

        return await self._run_in_executor(_merge)

    async def _overlay(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _overlay() -> PILImage.Image:
            canvas  = image.convert("RGBA")
            overlay = params["overlay"].convert("RGBA")

            if params["width"] is not None or params["height"] is not None:
                if params["width"] is None:
                    height = params["height"]
                    width  = max(1, round(overlay.width * height / overlay.height))
                elif params["height"] is None:
                    width  = params["width"]
                    height = max(1, round(overlay.height * width / overlay.width))
                else:
                    width  = params["width"]
                    height = params["height"]

                overlay = overlay.resize((width, height), PILImage.Resampling.LANCZOS)

            if params["opacity"] < 1.0:
                alpha = overlay.split()[3].point(lambda a: int(a * params["opacity"]))
                overlay.putalpha(alpha)

            offset_x, offset_y = self._resolve_anchor_offset(params["anchor"], params["x"], params["y"], overlay.size)
            canvas.alpha_composite(overlay, (offset_x, offset_y))

            if image.mode != "RGBA":
                return canvas.convert(image.mode)

            return canvas

        return await self._run_in_executor(_overlay)

    async def _mosaic(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _mosaic() -> PILImage.Image:
            mode    = params["mode"]
            regions = params["regions"]

            if regions is None:
                regions = [ ImageRegion(x=0, y=0, width=image.width, height=image.height) ]

            canvas = image.copy()

            for region in regions:
                cx1 = max(0, int(region.x))
                cy1 = max(0, int(region.y))
                cx2 = min(image.width,  int(region.x) + int(region.width))
                cy2 = min(image.height, int(region.y) + int(region.height))

                if cx2 <= cx1 or cy2 <= cy1:
                    continue

                target     = canvas.crop((cx1, cy1, cx2, cy2))
                block_size = None

                if mode == MosaicMode.PIXELATE:
                    block_size = params["block_size"]

                    if block_size is None:
                        block_size = round(min(target.size) * params["block_scale"])
                        block_size = min(params["max_block_size"], max(params["min_block_size"], block_size))

                    mosaic = self._mosaic_pixelate(target, block_size)
                elif mode == MosaicMode.BLUR:
                    mosaic = target.filter(ImageFilter.GaussianBlur(radius=params["blur_radius"]))
                else:
                    raise ValueError(f"Unsupported mosaic mode: {mode}")

                corner_radius = params["corner_radius"]

                if corner_radius is None:
                    corner_radius = round(min(target.size) * params["corner_scale"])

                if corner_radius > 0:
                    if mode == MosaicMode.PIXELATE:
                        mask = self._blocky_rounded_rectangle_mask(mosaic.size, corner_radius, block_size)
                    else:
                        mask = self._rounded_rectangle_mask(mosaic.size, corner_radius)
                    canvas.paste(mosaic, (cx1, cy1), mask)
                else:
                    canvas.paste(mosaic, (cx1, cy1))

            return canvas

        return await self._run_in_executor(_mosaic)

    def _concat_horizontal(self, images: List[PILImage.Image], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
        total_width = sum(image.width for image in images) + spacing * (len(images) - 1)
        max_height  = max(image.height for image in images)
        canvas      = PILImage.new("RGBA", (total_width, max_height), background)

        offset_x = 0
        for image in images:
            offset_y = (max_height - image.height) // 2
            canvas.paste(image, (offset_x, offset_y), image)
            offset_x += image.width + spacing

        return canvas

    def _concat_vertical(self, images: List[PILImage.Image], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
        max_width    = max(image.width for image in images)
        total_height = sum(image.height for image in images) + spacing * (len(images) - 1)
        canvas       = PILImage.new("RGBA", (max_width, total_height), background)

        offset_y = 0
        for image in images:
            offset_x = (max_width - image.width) // 2
            canvas.paste(image, (offset_x, offset_y), image)
            offset_y += image.height + spacing

        return canvas

    def _concat_grid(self, images: List[PILImage.Image], columns: Optional[int], rows: Optional[int], spacing: int, background: Tuple[int, int, int, int]) -> PILImage.Image:
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

    def _mosaic_pixelate(self, image: PILImage.Image, block_size: int) -> PILImage.Image:
        w, h = image.size
        shrunk_w = max(1, w // block_size)
        shrunk_h = max(1, h // block_size)

        shrunk = image.resize((shrunk_w, shrunk_h), PILImage.Resampling.BILINEAR)
        return shrunk.resize((w, h), PILImage.Resampling.NEAREST)

    def _blocky_rounded_rectangle_mask(self, size: Tuple[int, int], radius: int, block_size: int) -> PILImage.Image:
        width, height = size
        radius = min(max(0, radius), width // 2, height // 2)

        full = PILImage.new("L", size, 0)
        ImageDraw.Draw(full).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)

        cols = max(1, width  // block_size)
        rows = max(1, height // block_size)
        small = full.resize((cols, rows), PILImage.Resampling.NEAREST)

        return small.resize(size, PILImage.Resampling.NEAREST)

    def _rounded_rectangle_mask(self, size: Tuple[int, int], radius: int) -> PILImage.Image:
        width, height = size
        radius = min(radius, width // 2, height // 2)

        mask = PILImage.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)

        return mask

    def _resolve_anchor_point(self, anchor: ImagePositionAnchor, size: Tuple[int, int]) -> Tuple[int, int]:
        width, height = size
        vertical, horizontal = anchor.value.split("-") if "-" in anchor.value else (anchor.value, anchor.value)

        x = 0 if horizontal == "left" else width  if horizontal == "right"  else width  // 2
        y = 0 if vertical   == "top"  else height if vertical   == "bottom" else height // 2

        return (x, y)

    def _resolve_anchor_offset(self, anchor: ImagePositionAnchor, x: int, y: int, size: Tuple[int, int]) -> Tuple[int, int]:
        shift_x, shift_y = self._resolve_anchor_point(anchor, size)

        return (x - shift_x, y - shift_y)

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

    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeImageProcessorAction(action).run(context)
