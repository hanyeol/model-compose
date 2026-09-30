from __future__ import annotations

from typing import Optional, Dict, List, Tuple, Callable, Any
from mindor.dsl.schema.component import ImageDrawingComponentConfig
from mindor.dsl.schema.action import ImageDrawingActionConfig
from mindor.core.utils.text import contains_cjk_characters
from mindor.core.utils.font import find_cjk_font
from mindor.core.logger import logging
from ..base import ImageDrawingDriver, ImageDrawingDriverType, register_image_drawing_driver
from ..base import ComponentActionContext
from .common import ImageDrawingAction
from PIL import Image as PILImage, ImageDraw, ImageFont

class NativeImageDrawingAction(ImageDrawingAction):
    async def _point(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _point() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                None,
                lambda draw: draw.point(params["points"], fill=params["fill"]),
            )

        return await self._run_in_executor(_point)

    async def _line(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _line() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                None,
                lambda draw: draw.line(
                    params["points"],
                    fill=params["fill"],
                    width=params["line_width"],
                    joint=params["joint"],
                ),
            )

        return await self._run_in_executor(_line)

    async def _arc(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _arc() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                None,
                lambda draw: draw.arc(
                    self._bbox(params),
                    start=params["start"],
                    end=params["end"],
                    fill=params["fill"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_arc)

    async def _chord(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _chord() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                params["outline"],
                lambda draw: draw.chord(
                    self._bbox(params),
                    start=params["start"],
                    end=params["end"],
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_chord)

    async def _pieslice(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _pieslice() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                params["outline"],
                lambda draw: draw.pieslice(
                    self._bbox(params),
                    start=params["start"],
                    end=params["end"],
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_pieslice)

    async def _ellipse(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _ellipse() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                params["outline"],
                lambda draw: draw.ellipse(
                    self._bbox(params),
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_ellipse)

    async def _circle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _circle() -> PILImage.Image:
            x      = params["x"]
            y      = params["y"]
            radius = params["radius"]

            def _draw(draw: ImageDraw.ImageDraw) -> None:
                if hasattr(draw, "circle"):
                    draw.circle((x, y), radius, fill=params["fill"], outline=params["outline"], width=params["line_width"])
                else:
                    draw.ellipse(
                        [x - radius, y - radius, x + radius, y + radius],
                        fill=params["fill"],
                        outline=params["outline"],
                        width=params["line_width"],
                    )

            return self._draw_shape(image.copy(), params["fill"], params["outline"], _draw)

        return await self._run_in_executor(_circle)

    async def _rectangle(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _rectangle() -> PILImage.Image:
            bbox = self._bbox(params)

            def _draw(draw: ImageDraw.ImageDraw) -> None:
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

            return self._draw_shape(image.copy(), params["fill"], params["outline"], _draw)

        return await self._run_in_executor(_rectangle)

    async def _polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _polygon() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                params["outline"],
                lambda draw: draw.polygon(
                    params["points"],
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_polygon)

    async def _regular_polygon(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _regular_polygon() -> PILImage.Image:
            return self._draw_shape(
                image.copy(),
                params["fill"],
                params["outline"],
                lambda draw: draw.regular_polygon(
                    (params["x"], params["y"], params["radius"]),
                    n_sides=params["sides"],
                    rotation=params["rotation"],
                    fill=params["fill"],
                    outline=params["outline"],
                    width=params["line_width"],
                ),
            )

        return await self._run_in_executor(_regular_polygon)

    async def _text(self, image: PILImage.Image, params: Dict[str, Any]) -> PILImage.Image:
        def _text() -> PILImage.Image:
            canvas = image.copy()
            font   = self._load_font(params["font"], params["text"])
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
            font   = self._load_font(params["font"], params["text"])
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

    def _load_font(self, config: Optional[Dict[str, Any]], text: Optional[str] = None) -> Optional[ImageFont.ImageFont]:
        # User-supplied `path` wins even for CJK text — the caller made an
        # explicit choice and we shouldn't second-guess it. Fallback only
        # kicks in when no path was given and the text needs CJK coverage,
        # because PIL's default bitmap font is ASCII-only and would render
        # every Hangul/Han/Kana codepoint as a `.notdef` box.
        if config is None:
            config = {}

        path = config.get("path")
        size = config.get("size")

        if path:
            return ImageFont.truetype(
                path,
                size=size if size is not None else 10,
                index=config.get("index", 0),
                encoding=config.get("encoding", "unic"),
            )

        if contains_cjk_characters(text):
            font = find_cjk_font(size=size if size is not None else 16)

            if font is not None:
                return font

            logging.warning(
                "Text contains CJK characters but no font path was configured "
                "and no system CJK font was found; PIL's default font will "
                "render these characters as `.notdef` boxes."
            )

        if size is not None:
            try:
                return ImageFont.load_default(size=size)
            except TypeError:
                return ImageFont.load_default()

        return ImageFont.load_default()

    def _bbox(self, params: Dict[str, Any]) -> Tuple[float, float, float, float]:
        return (params["x"], params["y"], params["x"] + params["width"], params["y"] + params["height"])

    @classmethod
    def _draw_shape(
        cls,
        canvas: PILImage.Image,
        fill: Any,
        outline: Any,
        processor: Callable[[ImageDraw.ImageDraw], None],
    ) -> PILImage.Image:
        """Run `processor` on `canvas`, routing translucent paint through an
        alpha_composite layer so semi-transparent shapes actually blend.

        PIL's Draw.polygon/rectangle/etc. write RGBA fill straight into the
        target buffer, which means an (r,g,b,128) fill *replaces* the pixels
        underneath instead of mixing with them. Drawing on a fully-transparent
        RGBA overlay first and then compositing it produces the expected
        semi-transparent result. Opaque paint skips the overlay to avoid the
        allocation.
        """
        if cls._is_translucent(fill) or cls._is_translucent(outline):
            overlay = PILImage.new("RGBA", canvas.size, (0, 0, 0, 0))
            processor(ImageDraw.Draw(overlay))

            if canvas.mode != "RGBA":
                canvas = canvas.convert("RGBA")

            canvas.alpha_composite(overlay)

            return canvas

        processor(ImageDraw.Draw(canvas))

        return canvas

    @staticmethod
    def _is_translucent(color: Any) -> bool:
        """Return True when `color` carries an alpha channel with 0 < a < 255.

        Fully opaque and fully transparent both take the direct draw path —
        alpha_composite is only needed when the shape has to blend with what's
        underneath. Non-tuple colors (hex strings, None, palette indices) are
        treated as opaque because PIL parses them as such.
        """
        if isinstance(color, (tuple, list)) and len(color) == 4:
            return 0 < color[3] < 255

        return False

@register_image_drawing_driver(ImageDrawingDriverType.NATIVE)
class NativeImageDrawingService(ImageDrawingDriver):
    def __init__(self, id: str, config: ImageDrawingComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    async def _run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        return await NativeImageDrawingAction(action).run(context)
