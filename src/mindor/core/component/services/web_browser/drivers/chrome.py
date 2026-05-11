from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import ChromeWebBrowserComponentConfig, WebBrowserDriver
from mindor.core.utils.cdp_client import CdpClient
from ..base import WebBrowserService, WebBrowserSession, register_web_browser_service
import asyncio


class ChromeBrowserSession(WebBrowserSession):
    """Browser session backed by a persistent CDP connection."""

    def __init__(self, client: CdpClient):
        self.client = client
        self._lifecycle_enabled = False

    # ---- Navigation ----

    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        await self._ensure_page_enabled()

        loop = asyncio.get_running_loop()
        nav_done: asyncio.Future = loop.create_future()

        event_map = {
            "load": "Page.loadEventFired",
            "domcontentloaded": "Page.domContentEventFired",
            "networkidle": "Page.lifecycleEvent",
        }
        event_method = event_map.get(wait_until, "Page.loadEventFired")

        async def _on_event(params):
            if not nav_done.done():
                if wait_until == "networkidle":
                    if params.get("name") == "networkIdle":
                        nav_done.set_result(True)
                else:
                    nav_done.set_result(True)

        self.client.on_event(event_method, _on_event)
        try:
            result = await self.client.send_command("Page.navigate", {"url": url})
            await asyncio.wait_for(nav_done, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Navigation to '{url}' did not complete within {timeout}s")
        finally:
            self.client.remove_event_listener(event_method, _on_event)

        return {"url": url, "frameId": result.get("frameId")}

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
            cx, cy = int(x), int(y)
        else:
            cx, cy = await self._get_element_center(selector, xpath, timeout)

        for event in ("mousePressed", "mouseReleased"):
            await self.client.send_command("Input.dispatchMouseEvent", {
                "type": event, "x": cx, "y": cy, "button": "left", "clickCount": 1
            })

        return { "x": cx, "y": cy }

    async def input(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        text: str,
        clear_first: bool,
        timeout: float
    ) -> Dict[str, Any]:
        cx, cy = await self._get_element_center(selector, xpath, timeout)

        # Focus element by clicking
        for event_type in ("mousePressed", "mouseReleased"):
            await self.client.send_command("Input.dispatchMouseEvent", {
                "type": event_type, "x": cx, "y": cy, "button": "left", "clickCount": 1
            })

        if clear_first:
            # Select all and delete
            await self.client.send_command("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "a", "modifiers": 2  # Ctrl+A
            })
            await self.client.send_command("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "a", "modifiers": 2
            })
            await self.client.send_command("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "Backspace"
            })
            await self.client.send_command("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "Backspace"
            })

        for char in text:
            await self.client.send_command("Input.dispatchKeyEvent", {
                "type": "char", "text": char
            })

        return { "typed": text }

    async def scroll(self, selector: Optional[str], x: int, y: int) -> Dict[str, Any]:
        if selector:
            js = f"""(function() {{
                const el = document.querySelector({repr(selector)});
                if (el) el.scrollBy({x}, {y});
            }})()"""
        else:
            js = f"window.scrollBy({x}, {y})"

        await self.client.send_command("Runtime.evaluate", { "expression": js, "returnByValue": True })
        return { "scrolled_x": x, "scrolled_y": y }

    # ---- Query ----

    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> Dict[str, Any]:
        js = self._build_wait_condition_js(selector, xpath, condition)
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            result = await self.client.send_command("Runtime.evaluate", {
                "expression": js, "returnByValue": True
            })
            value = result.get("result", {}).get("value")
            if value:
                return {"found": True}
            await asyncio.sleep(0.3)

        target = selector or xpath
        raise TimeoutError(f"wait_for '{target}' ({condition}) timed out after {timeout}s")

    async def extract(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        js = self._build_extract_js(selector, xpath, extract_mode, attribute, multiple)
        result = await self.client.send_command("Runtime.evaluate", {
            "expression": js, "returnByValue": True
        })
        if "exceptionDetails" in result:
            raise RuntimeError(f"Extract JavaScript error: { result['exceptionDetails'] }")
        return result.get("result", {}).get("value")

    async def evaluate(self, expression: str) -> Any:
        result = await self.client.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })

        if "exceptionDetails" in result:
            raise RuntimeError(f"JavaScript error: { result['exceptionDetails'] }")

        return result.get("result", {}).get("value")

    # ---- Capture ----

    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> str:
        params: Dict[str, Any] = {"format": format}
        if format == "jpeg" and quality is not None:
            params["quality"] = int(quality)
        if full_page:
            params["captureBeyondViewport"] = True
        if selector:
            box = await self._find_element_bounding_box(selector, None)
            if box:
                params["clip"] = {**box, "scale": 1}

        result = await self.client.send_command("Page.captureScreenshot", params)
        return result["data"]  # base64-encoded

    # ---- State ----

    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        params = {}
        if urls:
            params["urls"] = urls
        result = await self.client.send_command("Network.getCookies", params)
        return result.get("cookies", [])

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        await self.client.send_command("Network.setCookies", {"cookies": cookies})
        return {"set": len(cookies)}

    # ---- Lifecycle ----

    async def close(self) -> None:
        await self.client.close()

    # ---- Internal helpers ----

    async def _ensure_page_enabled(self) -> None:
        await self.client.send_command("Page.enable")
        if not self._lifecycle_enabled:
            await self.client.send_command("Page.setLifecycleEventsEnabled", {"enabled": True})
            self._lifecycle_enabled = True

    async def _get_element_center(self, selector: Optional[str], xpath: Optional[str], timeout: float) -> tuple:
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            box = await self._find_element_bounding_box(selector, xpath)
            if box:
                cx = int(box["x"] + box["width"] / 2)
                cy = int(box["y"] + box["height"] / 2)
                return cx, cy
            await asyncio.sleep(0.3)

        target = selector or xpath
        raise TimeoutError(f"Element '{target}' not found within {timeout}s")

    async def _find_element_bounding_box(self, selector: Optional[str], xpath: Optional[str]) -> Optional[Dict]:
        if selector:
            js = f"""(function() {{
                const el = document.querySelector({repr(selector)});
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{x: r.left, y: r.top, width: r.width, height: r.height}};
            }})()"""
        else:
            js = f"""(function() {{
                const result = document.evaluate({repr(xpath)}, document, null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE, null);
                const el = result.singleNodeValue;
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {{x: r.left, y: r.top, width: r.width, height: r.height}};
            }})()"""

        result = await self.client.send_command("Runtime.evaluate", {
            "expression": js, "returnByValue": True
        })
        return result.get("result", {}).get("value")

    def _build_wait_condition_js(self, selector: Optional[str], xpath: Optional[str], condition: str) -> str:
        if selector:
            target_js = f"document.querySelector({repr(selector)})"
        else:
            target_js = (f"document.evaluate({repr(xpath)}, document, null, "
                         f"XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue")

        if condition == "present":
            return f"!!({target_js})"
        if condition == "visible":
            return f"""(function() {{
                const el = {target_js};
                if (!el) return false;
                const s = window.getComputedStyle(el);
                return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            }})()"""
        if condition == "hidden":
            return f"""(function() {{
                const el = {target_js};
                if (!el) return true;
                const s = window.getComputedStyle(el);
                return s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0';
            }})()"""
        return "true"

    def _build_extract_js(self, selector: Optional[str], xpath: Optional[str],
                          extract_mode: str, attribute: Optional[str], multiple: bool) -> str:
        if selector:
            if multiple:
                get_els = f"Array.from(document.querySelectorAll({repr(selector)}))"
            else:
                get_els = f"[document.querySelector({repr(selector)})].filter(Boolean)"
        else:
            if multiple:
                get_els = f"""(function() {{
                    const r = document.evaluate({repr(xpath)}, document, null,
                        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                    return Array.from({{length: r.snapshotLength}}, (_, i) => r.snapshotItem(i));
                }})()"""
            else:
                get_els = (f"[document.evaluate({repr(xpath)}, document, null, "
                           f"XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue].filter(Boolean)")

        if extract_mode == "text":
            map_fn = "el => el.innerText || el.textContent || ''"
        elif extract_mode == "html":
            map_fn = "el => el.outerHTML"
        else:  # attribute
            map_fn = f"el => el.getAttribute({repr(attribute)})"

        if multiple:
            return f"({get_els}).map({map_fn})"
        else:
            return f"""(function() {{ const els = {get_els}; return els.length ? ({get_els}).map({map_fn})[0] : null; }})()"""


@register_web_browser_service(WebBrowserDriver.CHROME)
class ChromeWebBrowserService(WebBrowserService):
    async def create_session(self) -> ChromeBrowserSession:
        if self.config.endpoint:
            client = CdpClient(self.config.endpoint)
            await client.connect()
        else:
            client = await CdpClient.discover(
                self.config.host, self.config.port, self.config.target_index
            )
        return ChromeBrowserSession(client)
