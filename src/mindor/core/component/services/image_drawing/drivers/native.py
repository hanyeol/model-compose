from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Any
from mindor.dsl.schema.component import ImageDrawingComponentConfig
from mindor.dsl.schema.action import ImageDrawingActionConfig
from ..base import ImageDrawingService, ImageDrawingDriver, register_image_drawing_service
from ..base import ComponentActionContext
from .common import ImageDrawingAction
from PIL import Image as PILImage, ImageDraw, ImageFont

class NativeImageDrawingAction(ImageDrawingAction):
    async def _point(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _point() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).point(params["points"], fill=params["fill"])
            return canvas

        return await self._run_in_executor(_point)

    async def _line(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _line() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).line(
                params["points"],
                fill=params["fill"],
                width=params["line_width"],
                joint=params["joint"],
            )
            return canvas

        return await self._run_in_executor(_line)

    async def _arc(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _arc() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).arc(
                self._bbox(params),
                start=params["start"],
                end=params["end"],
                fill=params["fill"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_arc)

    async def _chord(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _chord() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).chord(
                self._bbox(params),
                start=params["start"],
                end=params["end"],
                fill=params["fill"],
                outline=params["outline"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_chord)

    async def _pieslice(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _pieslice() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).pieslice(
                self._bbox(params),
                start=params["start"],
                end=params["end"],
                fill=params["fill"],
                outline=params["outline"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_pieslice)

    async def _ellipse(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _ellipse() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).ellipse(
                self._bbox(params),
                fill=params["fill"],
                outline=params["outline"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_ellipse)

    async def _circle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _circle() -> PILImage.Image:
            canvas = image.copy()
            draw   = ImageDraw.Draw(canvas)
            x      = params["x"]
            y      = params["y"]
            radius = params["radius"]

            if hasattr(draw, "circle"):
                draw.circle((x, y), radius, fill=params["fill"], outline=params["outline"], width=params["line_width"])
            else:
                draw.ellipse(
                    [x - radius, y - radius, x + radius, y + radius],
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                )
            return canvas

        return await self._run_in_executor(_circle)

    async def _rectangle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _rectangle() -> PILImage.Image:
            canvas = image.copy()
            draw   = ImageDraw.Draw(canvas)
            bbox   = self._bbox(params)

            if params["radius"]:
                kwargs: Dict[str, Any] = {
                    "radius":  params["radius"],
                    "fill":    params["fill"],
                    "outline": params["outline"],
                    "width":   params["line_width"],
                }

                if params["corners"] is not None:
                    kwargs["corners"] = params["corners"]

                draw.rounded_rectangle(bbox, **kwargs)
            else:
                draw.rectangle(
                    bbox,
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                )

            return canvas

        return await self._run_in_executor(_rectangle)

    async def _polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _polygon() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).polygon(
                params["points"],
                fill=params["fill"],
                outline=params["outline"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_polygon)

    async def _regular_polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _regular_polygon() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).regular_polygon(
                (params["x"], params["y"], params["radius"]),
                n_sides=params["sides"],
                rotation=params["rotation"],
                fill=params["fill"],
                outline=params["outline"],
                width=params["line_width"],
            )
            return canvas

        return await self._run_in_executor(_regular_polygon)

    async def _text(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _text() -> PILImage.Image:
            canvas = image.copy()
            font   = self._load_font(params["font"])
            ImageDraw.Draw(canvas).text(
                (params["x"], params["y"]),
                params["text"],
                fill=params["fill"],
                font=font,
                anchor=params["anchor"],
                spacing=params["spacing"],
                align=params["align"],
                stroke_width=params["stroke_width"],
                stroke_fill=params["stroke_fill"],
            )
            return canvas

        return await self._run_in_executor(_text)

    async def _multiline_text(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _multiline_text() -> PILImage.Image:
            canvas = image.copy()
            font   = self._load_font(params["font"])
            ImageDraw.Draw(canvas).multiline_text(
                (params["x"], params["y"]),
                params["text"],
                fill=params["fill"],
                font=font,
                anchor=params["anchor"],
                spacing=params["spacing"],
                align=params["align"],
                stroke_width=params["stroke_width"],
                stroke_fill=params["stroke_fill"],
            )
            return canvas

        return await self._run_in_executor(_multiline_text)

    async def _bitmap(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _bitmap() -> PILImage.Image:
            canvas = image.copy()
            ImageDraw.Draw(canvas).bitmap(
                (params["x"], params["y"]),
                params["bitmap"],
                fill=params["fill"],
            )
            return canvas

        return await self._run_in_executor(_bitmap)

    def _load_font(self, config: Optional[Dict[str, Any]]) -> Optional[ImageFont.ImageFont]:
        if config is None:
            return None

        path = config.get("path")
        size = config.get("size")

        if path:
            return ImageFont.truetype(
                path,
                size=size if size is not None else 10,
                index=config.get("index", 0),
                encoding=config.get("encoding", "unic"),
            )

        if size is not None:
            try:
                return ImageFont.load_default(size=size)
            except TypeError:
                return ImageFont.load_default()

        return ImageFont.load_default()

    def _bbox(self, params: Dict[str, Any]) -> Tuple[float, float, float, float]:
        return (params["x"], params["y"], params["x"] + params["width"], params["y"] + params["height"])

@register_image_drawing_service(ImageDrawingDriver.NATIVE)
class NativeImageDrawingService(ImageDrawingService):
    def __init__(self, id: str, config: ImageDrawingComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        return await NativeImageDrawingAction(action).run(context)
