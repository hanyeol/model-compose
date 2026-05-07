from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import PlaywrightWebBrowserComponentConfig, WebBrowserDriver
from ..base import WebBrowserService, WebBrowserSession, register_web_browser_service


class PlaywrightBrowserSession(WebBrowserSession):
    """Browser session backed by a Playwright page."""

    def __init__(self, browser: Any, page: Any):
        self._browser = browser
        self._page = page

    # ---- Navigation ----

    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        response = await self._page.goto(url, wait_until=wait_until, timeout=timeout * 1000)
        return { "url": url, "status": response.status if response else None }

    # ---- Interaction ----

    async def click(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int],
        timeout: float
    ) -> Dict[str, Any]:
        if x is not None and y is not None:
            await self._page.mouse.click(x, y)
            return {"x": x, "y": y}

        locator = self._resolve_locator(selector, xpath)
        box = await locator.bounding_box(timeout=timeout * 1000)
        if not box:
            target = selector or xpath
            raise TimeoutError(f"Element '{target}' not found within {timeout}s")
        cx = int(box["x"] + box["width"] / 2)
        cy = int(box["y"] + box["height"] / 2)
        await self._page.mouse.click(cx, cy)
        return {"x": cx, "y": cy}

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
        return {"typed": text}

    async def scroll(self, selector: Optional[str], x: int, y: int) -> Dict[str, Any]:
        if selector:
            await self._page.evaluate(
                f"""(function() {{
                    const el = document.querySelector({repr(selector)});
                    if (el) el.scrollBy({x}, {y});
                }})()"""
            )
        else:
            await self._page.evaluate(f"window.scrollBy({x}, {y})")
        return {"scrolled_x": x, "scrolled_y": y}

    # ---- Query ----

    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> Dict[str, Any]:
        locator = self._resolve_locator(selector, xpath)
        state_map = {
            "present": "attached",
            "visible": "visible",
            "hidden": "hidden",
        }
        state = state_map.get(condition, "visible")
        await locator.wait_for(state=state, timeout=timeout * 1000)
        return {"found": True}

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
            elements = await locator.all()
            results = []
            for el in elements:
                results.append(await self._extract_from_element(el, extract_mode, attribute))
            return results
        else:
            return await self._extract_from_element(locator.first, extract_mode, attribute)

    async def evaluate(self, expression: str) -> Any:
        return await self._page.evaluate(expression)

    # ---- Capture ----

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

    # ---- State ----

    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        context = self._page.context
        cookies = await context.cookies(urls or [])
        return cookies

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        context = self._page.context
        await context.add_cookies(cookies)
        return { "set": len(cookies) }

    # ---- Lifecycle ----

    async def close(self) -> None:
        await self._browser.close()

    # ---- Internal helpers ----

    def _resolve_locator(self, selector: Optional[str], xpath: Optional[str]) -> Any:
        if selector:
            return self._page.locator(selector)
        return self._page.locator(f"xpath={xpath}")

    async def _extract_from_element(self, el: Any, extract_mode: str, attribute: Optional[str]) -> Any:
        if extract_mode == "text":
            return await el.inner_text()
        if extract_mode == "html":
            return await el.evaluate("el => el.outerHTML")
        # attribute
        return await el.get_attribute(attribute)


@register_web_browser_service(WebBrowserDriver.PLAYWRIGHT)
class PlaywrightWebBrowserService(WebBrowserService):
    async def create_session(self) -> PlaywrightBrowserSession:
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()

        launcher = getattr(pw, self.config.browser)
        browser = await launcher.launch(headless=self.config.headless, args=self.config.args or None)
        page = await browser.new_page()

        return PlaywrightBrowserSession(browser, page)
