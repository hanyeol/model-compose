from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from collections.abc import AsyncIterable, AsyncIterator
from mindor.dsl.schema.component import PlaywrightHtmlFrameRendererComponentConfig, HtmlFrameRendererDriver
from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from mindor.core.foundation.cancellation import CancellationToken
from mindor.core.foundation.streaming.image import load_image_from_bytes
from mindor.core.foundation.media.filename import format_filename
from mindor.core.utils.url import UrlResource
from mindor.core.logger import logging
from ..base import HtmlFrameRendererService, register_html_frame_renderer_service
from ..base import ComponentActionContext
from .common import HtmlFrameRendererAction, HtmlFrameRendererSession
from PIL import Image as PILImage
import json

class PlaywrightHtmlFrameRendererSession(HtmlFrameRendererSession):
    """Playwright-backed session. Owns a single page for the lifetime of one
    render call. The parent service owns the shared browser process."""
    def __init__(self, page: Any):
        self._page = page

    async def render_frames(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> AsyncIterator[Tuple[PILImage.Image, float]]:
        fps           = params["fps"]
        width         = params["width"]
        height        = params["height"]
        ready_timeout = params["ready_timeout"]

        await self._page.set_viewport_size({"width": width, "height": height})
        await self._inject_bootstrap(props)
        await self._page.goto(html.url)

        await self._page.wait_for_function(
            "typeof window.__renderer?.seek === 'function'",
            timeout=ready_timeout * 1000,
        )

        duration = await self._get_page_duration()
        frame_count = int(duration * fps)

        logging.debug("Capturing %d frames at %s fps (%.3fs)", frame_count, fps, duration)

        for index in range(frame_count):
            timestamp = index / fps
            await self._page.evaluate("(t) => window.__renderer.seek(t)", timestamp)
            image = await load_image_from_bytes(await self._page.screenshot(type="png"))
            yield image, timestamp

    async def close(self) -> None:
        try:
            await self._page.close()
        except Exception:  # noqa: BLE001 — page already closed / browser gone
            pass

    async def _inject_bootstrap(self, props: Optional[Dict[str, Any]]) -> None:
        """Seed window.__renderer before any page script runs.

        - `props` (if given) becomes ``window.__renderer.props``,
          giving the page read-only access to workflow-provided data.
        """
        scripts = [ "window.__renderer = window.__renderer || {};" ]

        if props is not None:
            scripts.append(f"window.__renderer.props = {json.dumps(props)};")

        await self._page.add_init_script("".join(scripts))

    async def _get_page_duration(self) -> float:
        duration = await self._page.evaluate("() => window.__renderer?.duration ?? null")

        if duration is None or duration <= 0:
            raise ValueError("duration is required. Set window.__renderer.duration in the page.")

        return duration

class PlaywrightHtmlFrameRendererAction(HtmlFrameRendererAction):
    def __init__(
        self,
        config: HtmlFrameRendererActionConfig,
        html_resolver,
        session_factory,
    ):
        super().__init__(config, html_resolver)

        self.session_factory = session_factory

    async def _render_batch(
        self,
        htmls: List[UrlResource],
        props: Optional[List[Optional[Dict[str, Any]]]],
        params: Dict[str, Any],
        streaming: bool,
        cancellation_token: Optional[CancellationToken] = None,
    ) -> List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]]:
        results: List[Union[List[Dict[str, Any]], AsyncIterable[Dict[str, Any]]]] = []

        for html, props in zip(htmls, props if props is not None else [ None ] * len(htmls)):
            session = await self.session_factory()
            if streaming:
                results.append(self._stream_frames(session, html, props, params))
            else:
                results.append(await self._collect_frames(session, html, props, params))

        return results

    async def _collect_frames(
        self,
        session: HtmlFrameRendererSession,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        filename_format = params["filename_format"]

        try:
            frames: List[Dict[str, Any]] = []
            async for image, timestamp in session.render_frames(html, props, params):
                frame_count = len(frames) + 1
                frame: Dict[str, Any] = {
                    "number":    frame_count,
                    "image":     image,
                    "timestamp": timestamp,
                }

                if filename_format is not None:
                    frame["filename"] = format_filename(filename_format, frame_count)

                frames.append(frame)
            return frames
        finally:
            await session.close()

    async def _stream_frames(
        self,
        session: HtmlFrameRendererSession,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> AsyncIterator[Dict[str, Any]]:
        filename_format = params["filename_format"]
        frame_count = 0

        try:
            async for image, timestamp in session.render_frames(html, props, params):
                frame_count += 1
                frame: Dict[str, Any] = {
                    "number":    frame_count,
                    "image":     image,
                    "timestamp": timestamp,
                }

                if filename_format is not None:
                    frame["filename"] = format_filename(filename_format, frame_count)

                yield frame
        finally:
            await session.close()

@register_html_frame_renderer_service(HtmlFrameRendererDriver.PLAYWRIGHT)
class PlaywrightHtmlFrameRendererService(HtmlFrameRendererService):
    config: PlaywrightHtmlFrameRendererComponentConfig

    def __init__(self, id: str, config: PlaywrightHtmlFrameRendererComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._playwright = None
        self._browser = None

    async def _run(self, action: HtmlFrameRendererActionConfig, context: ComponentActionContext) -> Any:
        return await PlaywrightHtmlFrameRendererAction(action, self._resolve_html, self._create_session).run(context)

    async def _create_session(self) -> PlaywrightHtmlFrameRendererSession:
        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None:
            self._browser = await self._playwright.chromium.launch(
                headless=self.config.headless,
            )

        page = await self._browser.new_page()
        return PlaywrightHtmlFrameRendererSession(page)

    async def _close_browser(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
