from __future__ import annotations

from typing import Optional, Tuple, Dict, List, Any, Union
from mindor.dsl.schema.component import MusicScoreRendererComponentConfig, MusicScoreRendererDriverType
from mindor.dsl.schema.action import MusicScoreRendererActionConfig, VerovioMusicScoreRendererActionConfig
from mindor.dsl.schema.action.impl.music_score_renderer.impl.common import (
    MusicScoreRendererFormat,
    MusicScoreRendererMarginConfig,
)
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.resources import StreamResource, save_stream_to_temporary_file
from mindor.core.foundation.streaming.resolver import resolve_stream_resource
from mindor.core.foundation.cancellation import CancellationToken
from ..base import MusicScoreRendererDriver, register_music_score_renderer_driver
from ..base import ComponentActionContext
from .common import MusicScoreRendererAction
import asyncio, io, os

_SVG_CONTENT_TYPE = "image/svg+xml"
_PDF_CONTENT_TYPE = "application/pdf"

class VerovioMusicScoreRendererAction(MusicScoreRendererAction):
    config: VerovioMusicScoreRendererActionConfig

    async def _prepare_input(self, context: ComponentActionContext) -> Any:
        return await context.render_variable(self.config.source)

    async def _resolve_params(self, context: ComponentActionContext) -> Dict[str, Any]:
        params = await super()._resolve_params(context)

        format      = await context.render_variable(self.config.format)
        page_width  = await context.render_scalar(self.config.page_width, float, 2100.0)
        page_height = await context.render_scalar(self.config.page_height, float, 2970.0)
        scale       = await context.render_scalar(self.config.scale, int, 100)
        margin      = await self._resolve_margin(context)
        dpi         = await context.render_scalar(self.config.dpi, int, 150)

        try:
            format = MusicScoreRendererFormat(format)
        except ValueError:
            raise ValueError(f"Unsupported format for music-score-renderer: {format!r}")

        params.update({
            "format":      format,
            "page_width":  page_width,
            "page_height": page_height,
            "scale":       scale,
            "margin":      margin,
            "dpi":     dpi,
        })

        return params

    async def _resolve_margin(self, context: ComponentActionContext) -> Dict[str, float]:
        margin = await context.render_variable(self.config.margin)
        sides = ("top", "right", "bottom", "left")

        if margin is None or isinstance(margin, (int, float)):
            margin = { side: margin if margin is not None else 50.0 for side in sides }
        
        if isinstance(margin, MusicScoreRendererMarginConfig):
            margin = margin.model_dump()
        
        if isinstance(margin, dict):
            return { side: float(margin.get(side, 50.0)) for side in sides }

        raise ValueError(f"Unsupported margin shape: {type(margin).__name__}")

    async def _render_batch(
        self,
        sources: List[Any],
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[List[StreamResource]]:
        return await asyncio.gather(*[
            self._render(source, params, cancellation_token) for source in sources
        ])

    async def _render(
        self,
        source: Any,
        params: Dict[str, Any],
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[StreamResource]:
        path, spooled = await self._resolve_source_path(source)

        try:
            svg_pages = await asyncio.to_thread(self._render_svg_pages, path, params)
        finally:
            if spooled:
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass

        return await self._encode_svg_pages(svg_pages, params["format"], params["dpi"])

    async def _resolve_source_path(self, source: Any) -> Tuple[str, bool]:
        """Turn the rendered stream into a filesystem path verovio can read.

        Returns ``(path, spooled)``. When ``spooled`` is True the caller must
        remove ``path`` after use. Raw str/bytes/UploadFile inputs are
        promoted via ``resolve_stream_resource`` so the YAML author does not
        have to cast with ``${... as file}`` for every source shape.
        """
        if not isinstance(source, StreamResource):
            source = await resolve_stream_resource(source)

        if isinstance(source, FileStreamResource):
            return os.path.expanduser(source.path), False

        return await save_stream_to_temporary_file(source, "musicxml"), True

    async def _encode_svg_pages(
        self,
        svg_pages: List[str],
        format: MusicScoreRendererFormat,
        dpi: int,
    ) -> List[StreamResource]:
        if format == MusicScoreRendererFormat.SVG:
            return [
                BytesStreamResource(svg.encode("utf-8"), content_type=_SVG_CONTENT_TYPE, filename=f"page-{index + 1}.svg")
                for index, svg in enumerate(svg_pages)
            ]

        if format == MusicScoreRendererFormat.PDF:
            return await asyncio.to_thread(self._svg_pages_to_pdf, svg_pages)

        if format == MusicScoreRendererFormat.PNG:
            return await asyncio.to_thread(self._svg_pages_to_png, svg_pages, dpi)

        raise ValueError(f"Unsupported music score renderer format: {format!r}")

    @staticmethod
    def _render_svg_pages(path: str, params: Dict[str, Any]) -> List[str]:
        import verovio

        toolkit = verovio.toolkit()
        toolkit.setOptions({
            "pageWidth":        params["page_width"],
            "pageHeight":       params["page_height"],
            "scale":            params["scale"],
            "pageMarginTop":    params["margin"]["top"],
            "pageMarginRight":  params["margin"]["right"],
            "pageMarginBottom": params["margin"]["bottom"],
            "pageMarginLeft":   params["margin"]["left"],
            "footer":           "none",
            "header":           "none",
        })

        if not toolkit.loadFile(path):
            raise ValueError(f"Verovio failed to parse MusicXML source: {path!r}")

        page_count = toolkit.getPageCount()

        return [ toolkit.renderToSVG(page) for page in range(1, page_count + 1) ]

    @staticmethod
    def _svg_pages_to_pdf(svg_pages: List[str]) -> List[StreamResource]:
        from reportlab.graphics import renderPDF
        from svglib.svglib import svg2rlg

        results: List[StreamResource] = []

        for index, svg in enumerate(svg_pages):
            drawing = svg2rlg(io.StringIO(svg))
            buffer = io.BytesIO()

            renderPDF.drawToFile(drawing, buffer)

            results.append(BytesStreamResource(
                buffer.getvalue(),
                content_type=_PDF_CONTENT_TYPE,
                filename=f"page-{index + 1}.pdf",
            ))

        return results

    @staticmethod
    def _svg_pages_to_png(svg_pages: List[str], dpi: int) -> List[StreamResource]:
        import resvg_py

        results: List[StreamResource] = []

        for index, svg in enumerate(svg_pages):
            png_bytes = resvg_py.svg_to_bytes(svg_string=svg, dpi=float(dpi))

            if isinstance(png_bytes, list):
                png_bytes = bytes(png_bytes)

            results.append(ImageStreamResource(
                png_bytes,
                format="png",
                filename=f"page-{index + 1}.png",
            ))

        return results


@register_music_score_renderer_driver(MusicScoreRendererDriverType.VEROVIO)
class VerovioMusicScoreRendererService(MusicScoreRendererDriver):
    def __init__(self, id: str, config: MusicScoreRendererComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "verovio", "svglib", "reportlab", "resvg-py" ]

    async def _run(self, action: MusicScoreRendererActionConfig, context: ComponentActionContext) -> Any:
        return await VerovioMusicScoreRendererAction(action).run(context)
