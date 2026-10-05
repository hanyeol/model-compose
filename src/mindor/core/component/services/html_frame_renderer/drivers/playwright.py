from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Union
from mindor.dsl.schema.component import PlaywrightHtmlFrameRendererComponentConfig, HtmlFrameRendererDriverType
from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.utils.playwright import install_browser
from mindor.core.utils.url import UrlResource
from mindor.core.logger import logging
from ..base import HtmlFrameRendererDriver, register_html_frame_renderer_driver
from ..base import ComponentActionContext
from .common import HtmlFrameRendererAction, HtmlFrameRendererSession
import asyncio, json

class PlaywrightHtmlFrameRendererSession(HtmlFrameRendererSession):
    """Playwright-backed session. Owns a single page; the orchestrator uses
    many sessions in parallel to render frames out of order. All push /
    fallback state lives on `self` so each session decides independently."""
    def __init__(self, page: Any):
        self._page = page
        self._render_signals: asyncio.Queue = asyncio.Queue()
        self._screenshot_params: Dict[str, Any] = {}
        self._render_timeout: float = 0.0
        self._use_render_signal: bool = True
        self._first_frame: bool = True

    async def load_html(
        self,
        html: UrlResource,
        props: Optional[Dict[str, Any]],
        params: Dict[str, Any],
    ) -> None:
        duration       = params["duration"]
        width          = params["width"]
        height         = params["height"]
        format         = params["format"]
        quality        = params["quality"]
        transparent    = params["transparent"]
        ready_timeout  = params["ready_timeout"]
        self._render_timeout = params["render_timeout"]

        self._screenshot_params = { "type": format }

        if format == "jpeg" and quality is not None:
            self._screenshot_params["quality"] = quality

        if transparent:
            # `omit_background` only takes effect when the page's html/body
            # leave their background unset; otherwise the page color still
            # paints over the viewport. Documented in the component guide.
            self._screenshot_params["omit_background"] = True

        await self._page.set_viewport_size({"width": width, "height": height})
        await self._page.expose_binding("__renderer_frame_done", lambda source, t: self._render_signals.put_nowait(t))
        await self._inject_bootstrap(props, duration)
        await self._page.goto(html.url)

        # Wait for the page to declare it's ready for capture. The page is
        # responsible for awaiting its own async setup (webfonts, images,
        # textures, three.js scene load, ...) before flipping this flag.
        # The driver does not inspect any of those directly.
        await self._page.wait_for_function(
            "window.__renderer && window.__renderer.ready === true",
            timeout=ready_timeout * 1000,
        )

    async def render_frame(self, timestamp: float) -> ImageStreamResource:
        if self._use_render_signal:
            self._clear_render_signals()  # discard any stray rendered() calls from a previous frame
            render_task = asyncio.create_task(self._page.evaluate("(t) => window.render(t)", timestamp))

            try:
                # Wait for the page's rendered() signal. The render RPC returning
                # first just means the function call returned — the paint can
                # still be a rAF away, so keep waiting for rendered() up to the
                # remaining budget. We still watch `render_task` so navigation
                # errors (page closed, JS threw) surface instead of hanging.
                render_signal_task = asyncio.create_task(self._render_signals.get())
                deadline = asyncio.get_running_loop().time() + self._render_timeout
                render_done = False

                while True:
                    remaining_time = deadline - asyncio.get_running_loop().time()

                    if remaining_time <= 0:
                        render_signal_task.cancel()
                        raise asyncio.TimeoutError

                    pending = { render_signal_task } if render_done else { render_signal_task, render_task }
                    done, _ = await asyncio.wait(
                        pending,
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=remaining_time,
                    )

                    if render_signal_task in done:
                        render_signal_task.result()  # surfaces exceptions; discards the timestamp
                        break

                    if render_task in done:
                        # Re-raise render() errors; a plain success just means
                        # the RPC returned — keep waiting for rendered().
                        render_task.result()
                        render_done = True
                        continue

                    # Timeout.
                    render_signal_task.cancel()
                    raise asyncio.TimeoutError
            except asyncio.TimeoutError:
                if not self._first_frame:
                    # After this session's first frame the rendered() contract
                    # was proven, so a stall here is a real failure — don't
                    # silently switch modes mid-render.
                    raise RuntimeError(
                        f"Page stopped calling window.__renderer.rendered() within {self._render_timeout}s"
                    )

                logging.info("Page did not call window.__renderer.rendered(); falling back to sequential render/screenshot.")

                self._use_render_signal = False
                await render_task  # ensure render() finished before capturing
        else:
            await self._page.evaluate("(t) => window.render(t)", timestamp)

        self._first_frame = False
        frame_bytes = await self._page.screenshot(**self._screenshot_params)

        return ImageStreamResource(frame_bytes, format=self._screenshot_params["type"])

    async def close(self) -> None:
        try:
            await self._page.close()
        except Exception:  # noqa: BLE001 — page already closed / browser gone
            pass

    async def _inject_bootstrap(self, props: Optional[Dict[str, Any]], duration: float) -> None:
        """Seed window.__renderer before any page script runs.

        - `duration` becomes ``window.__renderer.duration`` so pages that need
          the total length (e.g. progress bars drawn as t/duration) can read
          it without duplicating the value.
        - `props` (if given) becomes ``window.__renderer.props``,
          giving the page read-only access to workflow-provided data.
        - `rendered(t)` bridges to the server binding so pages can push a
          "frame is painted" signal instead of forcing the server to await
          render()'s RPC response before requesting the screenshot.
        """
        scripts = [
            "window.__renderer = window.__renderer || {};",
            f"window.__renderer.duration = {json.dumps(duration)};",
            "window.__renderer.rendered = (t) => window.__renderer_frame_done(t);",
        ]

        if props is not None:
            scripts.append(f"window.__renderer.props = {json.dumps(props)};")

        await self._page.add_init_script("".join(scripts))

    def _clear_render_signals(self) -> None:
        while not self._render_signals.empty():
            try:
                self._render_signals.get_nowait()
            except asyncio.QueueEmpty:
                break

@register_html_frame_renderer_driver(HtmlFrameRendererDriverType.PLAYWRIGHT)
class PlaywrightHtmlFrameRendererService(HtmlFrameRendererDriver):
    config: PlaywrightHtmlFrameRendererComponentConfig

    def __init__(self, id: str, config: PlaywrightHtmlFrameRendererComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._playwright = None
        self._browser = None

    def _get_setup_requirements(self) -> Optional[List[Union[str, Tuple[str, List[str]]]]]:
        return [ "playwright" ]

    async def _setup(self) -> None:
        install_browser("chromium")

    async def _run(self, action: HtmlFrameRendererActionConfig, context: ComponentActionContext) -> Any:
        return await HtmlFrameRendererAction(action, self._resolve_html, self._create_session).run(context)

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
