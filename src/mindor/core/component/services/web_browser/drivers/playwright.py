from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import PlaywrightWebBrowserComponentConfig, WebBrowserDriver
from ..base import WebBrowserService, register_web_browser_service
from .common import WebBrowserSession

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

    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> str:
        import base64

        params: Dict[str, Any] = {"type": format, "full_page": full_page}
        if format == "jpeg" and quality is not None:
            params["quality"] = int(quality)

        if selector:
            locator = self._page.locator(selector)
            data = await locator.screenshot(**params)
        else:
            data = await self._page.screenshot(**params)

        return base64.b64encode(data).decode("ascii")

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
    def __init__(self, id: str, config: Any, daemon: bool):
        super().__init__(id, config, daemon)

        self._playwrite = None
        self._browser = None

    async def create_session(self) -> PlaywrightBrowserSession:
        if self._browser is None:
            from playwright.async_api import async_playwright

            self._playwrite = await async_playwright().start()
            launcher = getattr(self._playwrite, self.config.browser)
            self._browser = await launcher.launch(headless=self.config.headless, args=self.config.args or None)

        page = await self._browser.new_page()
        return PlaywrightBrowserSession(page)

    async def close_browser(self) -> None:
        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwrite:
            await self._playwrite.stop()
            self._playwrite = None
