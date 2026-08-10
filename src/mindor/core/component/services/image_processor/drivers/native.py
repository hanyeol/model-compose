from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig
from mindor.dsl.schema.action import ImageProcessorActionConfig, ImageProcessorActionMethod, ImageScaleMode, FlipDirection, ImageConcatMode, ImagePositionAnchor, ImageCompressStrategy, MosaicMode
from ..base import ImageProcessorService, ImageProcessorDriver, register_image_processor_service
from ..base import ComponentActionContext
from .common import ImageProcessorAction
from PIL import Image as PILImage, ImageFilter, ImageEnhance
import math, io, shutil, subprocess

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
                regions = [ { "x": 0, "y": 0, "width": image.width, "height": image.height } ]

            result = image.copy()

            for region in regions:
                cx1 = max(0, region["x"])
                cy1 = max(0, region["y"])
                cx2 = min(image.width,  region["x"] + region["width"])
                cy2 = min(image.height, region["y"] + region["height"])

                if cx2 <= cx1 or cy2 <= cy1:
                    continue

                crop = result.crop((cx1, cy1, cx2, cy2))

                if mode == MosaicMode.PIXELATE:
                    mosaic = self._mosaic_pixelate(crop, params["block_size"])
                elif mode == MosaicMode.BLUR:
                    mosaic = crop.filter(ImageFilter.GaussianBlur(radius=params["radius"]))
                else:
                    raise ValueError(f"Unsupported mosaic mode: {mode}")

                result.paste(mosaic, (cx1, cy1))

            return result

        return await self._run_in_executor(_mosaic)

    async def _compress(self, image: PILImage.Image, params: Dict[str, Any]) -> bytes:
        def _compress() -> bytes:
            strategy       = params["strategy"]
            strip_metadata = params["strip_metadata"]

            if strategy == ImageCompressStrategy.LOSSLESS:
                return self._compress_lossless(image, params, strip_metadata)

            if strategy == ImageCompressStrategy.OPTIMIZED:
                data = self._compress_lossless(image, params, strip_metadata=False)
                return self._compress_optimized(data, params, strip_metadata)

            if strategy == ImageCompressStrategy.QUANTIZED:
                data = self._compress_lossless(image, params, strip_metadata=False)
                return self._compress_quantized(data, params, strip_metadata)

            raise ValueError(f"Unsupported compress strategy: {strategy}")

        return await self._run_in_executor(_compress)

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

    def _mosaic_pixelate(self, region: PILImage.Image, block_size: int) -> PILImage.Image:
        w, h = region.size
        shrunk_w = max(1, w // block_size)
        shrunk_h = max(1, h // block_size)

        shrunk = region.resize((shrunk_w, shrunk_h), PILImage.Resampling.BILINEAR)
        return shrunk.resize((w, h), PILImage.Resampling.NEAREST)

    def _compress_lossless(self, image: PILImage.Image, params: Dict[str, Any], strip_metadata: bool) -> bytes:
        buffer = io.BytesIO()
        save_params = {
            "format": "PNG",
            "optimize": True,
            "compress_level": params["compress_level"],
        }

        if not strip_metadata and image.info:
            pnginfo = self._build_pnginfo(image.info)
            if pnginfo is not None:
                save_params["pnginfo"] = pnginfo

        image.save(buffer, **save_params)
        return buffer.getvalue()

    def _build_pnginfo(self, info: Dict[str, Any]) -> Optional[Any]:
        from PIL import PngImagePlugin

        pnginfo = PngImagePlugin.PngInfo()
        added = False
        for key, value in info.items():
            if isinstance(value, str):
                pnginfo.add_text(key, value)
                added = True

        return pnginfo if added else None

    def _compress_optimized(self, data: bytes, params: Dict[str, Any], strip_metadata: bool) -> bytes:
        import oxipng

        strip = oxipng.StripChunks.safe() if strip_metadata else oxipng.StripChunks.none()
        return oxipng.optimize_from_memory(data, level=params["level"], strip=strip)

    def _compress_quantized(self, data: bytes, params: Dict[str, Any], strip_metadata: bool) -> bytes:
        program = shutil.which("pngquant")

        if not program:
            raise RuntimeError("Compress strategy 'quantized' requires the 'pngquant' program in PATH.")

        command = [ program, "--speed", str(params["speed"]) ]

        if strip_metadata:
            command.append("--strip")

        quality = self._format_quality_range(params["min_quality"], params["max_quality"])
        if quality:
            command += [ "--quality", quality ]

        command += [ "--output", "-", "-" ]

        result = subprocess.run(command, input=data, capture_output=True, check=True)
        return result.stdout

    def _format_quality_range(self, min_quality: Optional[int], max_quality: Optional[int]) -> Optional[str]:
        if min_quality is None and max_quality is None:
            return None

        return f"{min_quality if min_quality is not None else 0}-{max_quality if max_quality is not None else 100}"

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

    def get_setup_requirements(self) -> Optional[List[str]]:
        requirements: List[str] = []

        if self._has_compress_strategy(ImageCompressStrategy.OPTIMIZED):
            requirements.append("pyoxipng")

        return requirements or None

    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await NativeImageProcessorAction(action).run(context)

    def _has_compress_strategy(self, strategy: ImageCompressStrategy) -> bool:
        for action in self.config.actions:
            if action.method == ImageProcessorActionMethod.COMPRESS and action.strategy == strategy:
                return True

        return False
