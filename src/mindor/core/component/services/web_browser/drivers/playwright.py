from typing import Optional, Dict, List, Callable, Awaitable, Any
from .common import VideoAudioEncodingParams
from mindor.dsl.schema.component import PlaywrightWebBrowserComponentConfig, WebBrowserDriver
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource
from mindor.core.foundation.streaming.video import VideoStreamResource
from ..base import WebBrowserService, register_web_browser_service
from .common import WebBrowserSession
from .utils.chrome import VideoRecorder, PageAdapter
from PIL import Image as PILImage
import io

class PlaywrightPageAdapter(PageAdapter):
    """Thin wrapper around a Playwright Page. Every method delegates directly."""

    def __init__(self, page: Any):
        self._page = page

    async def navigate(self, url: str) -> None:
        await self._page.goto(url)

    async def expose_binding(
        self,
        name: str,
        callback: Callable[..., Awaitable[None]],
    ) -> None:
        await self._page.expose_binding(name, callback)

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        if arg is None:
            return await self._page.evaluate(expression)
        return await self._page.evaluate(expression, arg)


class PlaywrightBrowserSession(WebBrowserSession):
    """Browser session backed by a Playwright page."""
    def __init__(self, page: Any):
        self._page = page

    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        response = await self._page.goto(url, wait_until=wait_until, timeout=timeout * 1000)

        return { "url": url, "status": response.status if response else None }

    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> None:
        locator = self._resolve_locator(selector, xpath)
        state_map = {
            "present": "attached",
            "visible": "visible",
            "hidden": "hidden",
        }
        state = state_map.get(condition, "visible")

        await locator.wait_for(state=state, timeout=timeout * 1000)

    async def extract(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        locator = self._resolve_locator(selector, xpath)

        if multiple:
            return [ await self._extract_from_element(element, extract_mode, attribute) for element in await locator.all() ]

        if await locator.count() == 0:
            return None

        return await self._extract_from_element(locator.first, extract_mode, attribute)

    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> PILImage.Image:
        params: Dict[str, Any] = { "type": format, "full_page": full_page }

        if format == "jpeg" and quality is not None:
            params["quality"] = int(quality)

        if selector:
            locator = self._page.locator(selector)
            data = await locator.screenshot(**params)
        else:
            data = await self._page.screenshot(**params)

        return PILImage.open(io.BytesIO(data))

    async def capture_video(
        self,
        url: Optional[str],
        selector: Optional[str],
        include_video_track: bool,
        include_audio_track: bool,
        encoding: Optional[VideoAudioEncodingParams],
        duration: Optional[float],
    ) -> VideoStreamResource:
        format = (encoding.format if encoding and encoding.format else "webm").lower()
        source = VideoRecorder(PlaywrightPageAdapter(self._page)).capture(
            url=url,
            selector=selector,
            include_video_track=include_video_track,
            include_audio_track=include_audio_track,
            encoding=encoding,
            duration=duration,
        )

        return VideoStreamResource(AsyncIterableStreamResource(source), format=format)

    async def click(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int],
        timeout: float
    ) -> Dict[str, Any]:
        cx, cy = await self._get_click_position(selector, xpath, x, y, timeout)
        await self._page.mouse.click(cx, cy)

        return { "x": cx, "y": cy }

    async def input(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        text: str,
        clear_first: bool,
        timeout: float
    ) -> Dict[str, Any]:
        locator = self._resolve_locator(selector, xpath)

        if clear_first:
            await locator.fill(text, timeout=timeout * 1000)
        else:
            await locator.press_sequentially(text, timeout=timeout * 1000)

        return { "typed": text }

    async def scroll(self, selector: Optional[str], xpath: Optional[str], x: Optional[int], y: Optional[int]) -> Dict[str, Any]:
        if selector is not None or xpath is not None:
            locator = self._resolve_locator(selector, xpath)

            if x is not None or y is not None:
                await locator.evaluate(f"element => element.scrollBy({x or 0}, {y or 0})")
            else:
                await locator.scroll_into_view_if_needed()
        else:
            await self._page.evaluate(f"window.scrollBy({x or 0}, {y or 0})")

        return { "scrolled_x": x, "scrolled_y": y }

    async def evaluate(self, expression: str) -> Any:
        return await self._page.evaluate(expression)

    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        return await self._page.context.cookies(urls or [])

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        await self._page.context.add_cookies(cookies)

    async def close(self) -> None:
        await self._page.close()

    def _resolve_locator(self, selector: Optional[str], xpath: Optional[str]) -> Any:
        if selector:
            return self._page.locator(selector)

        if xpath:
            return self._page.locator(f"xpath={xpath}")

        raise ValueError("Either 'selector' or 'xpath' must be provided.")

    async def _get_click_position(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int],
        timeout: float
    ) -> tuple:
        if selector is not None or xpath is not None:
            locator = self._resolve_locator(selector, xpath)
            box = await locator.bounding_box(timeout=timeout * 1000)

            if not box:
                target = selector or xpath
                raise TimeoutError(f"Element '{target}' not found within {timeout}s")

            return int(box["x"] + box["width"] / 2), int(box["y"] + box["height"] / 2)

        if x is not None and y is not None:
            return int(x), int(y)
        
        raise ValueError("One of 'selector', 'xpath', or coordinates('x' and 'y') must be provided.")

    async def _extract_from_element(self, element: Any, extract_mode: str, attribute: Optional[str]) -> Any:
        if extract_mode == "text":
            return await element.inner_text()

        if extract_mode == "html":
            return await element.evaluate("element => element.outerHTML")

        if extract_mode == "attribute":
            return await element.get_attribute(attribute)

        raise ValueError(f"Unsupported extract_mode: '{extract_mode}'.")

@register_web_browser_service(WebBrowserDriver.PLAYWRIGHT)
class PlaywrightWebBrowserService(WebBrowserService):
    config: PlaywrightWebBrowserComponentConfig

    def __init__(self, id: str, config: PlaywrightWebBrowserComponentConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self._playwright = None
        self._browser = None             # persistent-launch or CDP-attach browser wrapper
        self._persistent_context = None  # non-None only for launch_persistent_context
        self._attached = False           # True when connected via CDP; leave browser alive on close

    async def create_session(self) -> PlaywrightBrowserSession:
        from playwright.async_api import async_playwright

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        if self._browser is None and self._persistent_context is None:
            if self.config.cdp_url:
                self._browser = await self._playwright.chromium.connect_over_cdp(self.config.cdp_url)
                self._attached = True
            elif self.config.persistent_dir:
                launcher = getattr(self._playwright, self.config.browser)
                self._persistent_context = await launcher.launch_persistent_context(
                    user_data_dir=self.config.persistent_dir,
                    headless=self.config.headless,
                    args=self.config.args or None,
                    channel=self.config.channel,
                )
            else:
                launcher = getattr(self._playwright, self.config.browser)
                self._browser = await launcher.launch(
                    headless=self.config.headless,
                    args=self.config.args or None,
                    channel=self.config.channel,
                )

        if self._persistent_context is not None:
            page = await self._persistent_context.new_page()
        elif self._attached:
            context = self._browser.contexts[0] if self._browser.contexts else await self._browser.new_context()
            page = await context.new_page()
        else:
            page = await self._browser.new_page()

        return PlaywrightBrowserSession(page)

    async def close_browser(self) -> None:
        if self._persistent_context is not None:
            await self._persistent_context.close()
            self._persistent_context = None

        if self._browser is not None:
            # For CDP-attached browsers, close() only tears down our client; the
            # user's Chrome instance keeps running, which is the whole point of
            # attaching over CDP.
            await self._browser.close()
            self._browser = None
            self._attached = False

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
