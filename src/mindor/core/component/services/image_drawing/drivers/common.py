from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from abc import abstractmethod
from mindor.dsl.schema.action import (
    ImageDrawingActionConfig,
    ImageDrawingActionMethod,
    LineJoint,
    TextAlign,
    FontConfig,
)
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.utils.iterators import BatchSourceIterator
from mindor.core.logger import logging
from ..base import ComponentActionContext
from ....action.base import ComponentAction
from PIL import Image as PILImage
import asyncio

class ImageDrawingAction(ComponentAction):
    def __init__(self, config: ImageDrawingActionConfig):
        self.config: ImageDrawingActionConfig = config

    async def run(self, context: ComponentActionContext) -> Any:
        image      = await context.render_image(self.config.image)
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

    async def _resolve_params(self, method: ImageDrawingActionMethod, context: ComponentActionContext) -> Dict[str, Any]:
        if method == ImageDrawingActionMethod.POINT:
            points = await self._render_points(self.config.points, context)
            fill   = await context.render_scalar(self.config.fill, "color")

            return { "points": points, "fill": fill }

        if method == ImageDrawingActionMethod.LINE:
            points     = await self._render_points(self.config.points, context)
            fill       = await context.render_scalar(self.config.fill, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 0
            joint      = await context.render_variable(self.config.joint)

            if joint is not None:
                try:
                    joint = LineJoint(joint)
                except ValueError:
                    raise ValueError(f"Invalid line joint: {joint}")

            return {
                "points":     points,
                "fill":       fill,
                "line_width": line_width,
                "joint":      joint.value if isinstance(joint, LineJoint) else None,
            }

        if method == ImageDrawingActionMethod.ARC:
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            width      = await context.render_scalar(self.config.width, float)
            height     = await context.render_scalar(self.config.height, float)
            start      = await context.render_scalar(self.config.start, float)
            end        = await context.render_scalar(self.config.end, float)
            fill       = await context.render_scalar(self.config.fill, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 0

            return {
                "x":          x,
                "y":          y,
                "width":      width,
                "height":     height,
                "start":      start,
                "end":        end,
                "fill":       fill,
                "line_width": line_width,
            }

        if method in (ImageDrawingActionMethod.CHORD, ImageDrawingActionMethod.PIESLICE):
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            width      = await context.render_scalar(self.config.width, float)
            height     = await context.render_scalar(self.config.height, float)
            start      = await context.render_scalar(self.config.start, float)
            end        = await context.render_scalar(self.config.end, float)
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1

            return {
                "x":          x,
                "y":          y,
                "width":      width,
                "height":     height,
                "start":      start,
                "end":        end,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
            }

        if method == ImageDrawingActionMethod.ELLIPSE:
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            width      = await context.render_scalar(self.config.width, float)
            height     = await context.render_scalar(self.config.height, float)
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1

            return {
                "x":          x,
                "y":          y,
                "width":      width,
                "height":     height,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
            }

        if method == ImageDrawingActionMethod.CIRCLE:
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            radius     = await context.render_scalar(self.config.radius, float)
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1

            return {
                "x":          x,
                "y":          y,
                "radius":     radius,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
            }

        if method == ImageDrawingActionMethod.RECTANGLE:
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            width      = await context.render_scalar(self.config.width, float)
            height     = await context.render_scalar(self.config.height, float)
            radius     = await context.render_scalar(self.config.radius, float)
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1
            corners    = await context.render_variable(self.config.corners)

            if corners is not None:
                corners = tuple(bool(corner) for corner in corners)

                if len(corners) != 4:
                    raise ValueError(f"'corners' must be a sequence of 4 booleans, got {len(corners)}")

            return {
                "x":          x,
                "y":          y,
                "width":      width,
                "height":     height,
                "radius":     radius,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
                "corners":    corners,
            }

        if method == ImageDrawingActionMethod.POLYGON:
            points     = await self._render_points(self.config.points, context)
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1

            return {
                "points":     points,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
            }

        if method == ImageDrawingActionMethod.REGULAR_POLYGON:
            x          = await context.render_scalar(self.config.x, float)
            y          = await context.render_scalar(self.config.y, float)
            radius     = await context.render_scalar(self.config.radius, float)
            sides      = await context.render_scalar(self.config.sides, int)
            rotation   = await context.render_scalar(self.config.rotation, float) or 0
            fill       = await context.render_scalar(self.config.fill, "color")
            outline    = await context.render_scalar(self.config.outline, "color")
            line_width = await context.render_scalar(self.config.line_width, int) or 1

            if sides is None or sides < 3:
                raise ValueError(f"'sides' must be >= 3, got {sides}")

            return {
                "x":          x,
                "y":          y,
                "radius":     radius,
                "sides":      sides,
                "rotation":   rotation,
                "fill":       fill,
                "outline":    outline,
                "line_width": line_width,
            }

        if method in (ImageDrawingActionMethod.TEXT, ImageDrawingActionMethod.MULTILINE_TEXT):
            x            = await context.render_scalar(self.config.x, float)
            y            = await context.render_scalar(self.config.y, float)
            text         = await context.render_text(self.config.text) or ""
            fill         = await context.render_scalar(self.config.fill, "color")
            font         = await self._resolve_font(self.config.font, context) if self.config.font is not None else None
            anchor       = await context.render_variable(self.config.anchor)
            spacing      = await context.render_scalar(self.config.spacing, int) or 0
            align        = await context.render_variable(self.config.align)
            stroke_width = await context.render_scalar(self.config.stroke_width, int) or 0
            stroke_fill  = await context.render_scalar(self.config.stroke_fill, "color")

            try:
                align = TextAlign(align) if align is not None else TextAlign.LEFT
            except ValueError:
                raise ValueError(f"Invalid text align: {align}")

            return {
                "x":            x,
                "y":            y,
                "text":         text,
                "fill":         fill,
                "font":         font,
                "anchor":       anchor,
                "spacing":      spacing,
                "align":        align.value,
                "stroke_width": stroke_width,
                "stroke_fill":  stroke_fill,
            }

        if method == ImageDrawingActionMethod.BITMAP:
            x      = await context.render_scalar(self.config.x, float)
            y      = await context.render_scalar(self.config.y, float)
            bitmap = await context.render_image(self.config.bitmap)
            fill   = await context.render_scalar(self.config.fill, "color")

            if isinstance(bitmap, (list, StreamIterator, AsyncIterator)):
                raise ValueError("'bitmap' must resolve to a single image, not a batch or stream")

            return { "x": x, "y": y, "bitmap": bitmap, "fill": fill }

        raise ValueError(f"Unsupported image drawing action method: {method}")

    async def _render_points(self, value: Any, context: ComponentActionContext) -> Optional[List[Tuple[float, float]]]:
        value = await context.render_variable(value)

        if value is None:
            return None

        if not isinstance(value, (list, tuple)):
            raise ValueError(f"'points' must be a list of (x, y) pairs, got {type(value).__name__}")

        points: List[Tuple[float, float]] = []

        for point in value:
            if not isinstance(point, (list, tuple)) or len(point) != 2:
                raise ValueError(f"Each point must be a 2-element (x, y) sequence, got {point!r}")

            x = await context.render_scalar(point[0], float)
            y = await context.render_scalar(point[1], float)
            points.append((x, y))

        return points

    async def _resolve_font(self, config: FontConfig, context: ComponentActionContext) -> Dict[str, Any]:
        path     = await context.render_variable(config.path)
        size     = await context.render_scalar(config.size, int)
        index    = await context.render_scalar(config.index, int) or 0
        encoding = await context.render_variable(config.encoding) or "unic"

        return { "path": path, "size": size, "index": index, "encoding": encoding }

    async def _process_batch(
        self,
        method: ImageDrawingActionMethod,
        images: List[Optional[PILImage.Image]],
        params: Dict[str, Any],
    ) -> List[Optional[PILImage.Image]]:
        async def _process(image: Optional[PILImage.Image]) -> Optional[PILImage.Image]:
            if image is None:
                logging.debug("Image drawing (%s) skipped because no image was provided.", method)
                return None

            return await self._draw(method, image, params)

        return await asyncio.gather(*[ _process(image) for image in images ])

    async def _draw(self, method: ImageDrawingActionMethod, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        if method == ImageDrawingActionMethod.POINT:
            return await self._point(image, params)

        if method == ImageDrawingActionMethod.LINE:
            return await self._line(image, params)

        if method == ImageDrawingActionMethod.ARC:
            return await self._arc(image, params)

        if method == ImageDrawingActionMethod.CHORD:
            return await self._chord(image, params)

        if method == ImageDrawingActionMethod.PIESLICE:
            return await self._pieslice(image, params)

        if method == ImageDrawingActionMethod.ELLIPSE:
            return await self._ellipse(image, params)

        if method == ImageDrawingActionMethod.CIRCLE:
            return await self._circle(image, params)

        if method == ImageDrawingActionMethod.RECTANGLE:
            return await self._rectangle(image, params)

        if method == ImageDrawingActionMethod.POLYGON:
            return await self._polygon(image, params)

        if method == ImageDrawingActionMethod.REGULAR_POLYGON:
            return await self._regular_polygon(image, params)

        if method == ImageDrawingActionMethod.TEXT:
            return await self._text(image, params)

        if method == ImageDrawingActionMethod.MULTILINE_TEXT:
            return await self._multiline_text(image, params)

        if method == ImageDrawingActionMethod.BITMAP:
            return await self._bitmap(image, params)

        raise ValueError(f"Unsupported image drawing action method: {method}")

    @abstractmethod
    async def _point(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _line(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _arc(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _chord(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _pieslice(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _ellipse(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _circle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _rectangle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _regular_polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _text(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _multiline_text(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass

    @abstractmethod
    async def _bitmap(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        pass
