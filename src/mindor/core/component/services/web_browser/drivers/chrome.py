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
        await self.client.send_command("Page.enable")

        if not self._lifecycle_enabled:
            await self.client.send_command("Page.setLifecycleEventsEnabled", { "enabled": True })
            self._lifecycle_enabled = True

        result = await self.client.send_command("Page.navigate", { "url": url })

        event = {
            "load": "Page.loadEventFired",
            "domcontentloaded": "Page.domContentEventFired",
            "networkidle": "Page.lifecycleEvent",
        }.get(wait_until)

        if event:
            loop = asyncio.get_running_loop()
            nav_done: asyncio.Future = loop.create_future()

            async def _on_event(params):
                if not nav_done.done():
                    if wait_until == "networkidle":
                        if params.get("name") == "networkIdle":
                            nav_done.set_result(True)
                    else:
                        nav_done.set_result(True)

            self.client.on_event(event, _on_event)
            try:
                await asyncio.wait_for(nav_done, timeout=timeout)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Navigation to '{url}' did not complete within {timeout}s")
            finally:
                self.client.remove_event_listener(event, _on_event)

        return { "url": url, "frameId": result.get("frameId") }

    # ---- Query ----

    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> Dict[str, Any]:
        script = self._build_wait_condition_script(selector, xpath, condition)
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            result = await self.client.send_command("Runtime.evaluate", {
                "expression": script, "returnByValue": True
            })
            value = result.get("result", {}).get("value")
            if value:
                return {"found": True}
            await asyncio.sleep(0.3)

        target = selector or xpath
        raise TimeoutError(f"wait_for '{target}' ({condition}) timed out after {timeout}s")

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

    async def extract(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        script = self._build_extract_script(selector, xpath, extract_mode, attribute, multiple)
        result = await self.client.send_command("Runtime.evaluate", {
            "expression": script, "returnByValue": True
        })

        if "exceptionDetails" in result:
            raise RuntimeError(f"Extract JavaScript error: { result['exceptionDetails'] }")

        return result.get("result", {}).get("value")

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
        for event in ("mousePressed", "mouseReleased"):
            await self.client.send_command("Input.dispatchMouseEvent", {
                "type": event, "x": cx, "y": cy, "button": "left", "clickCount": 1
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

    async def scroll(self, selector: Optional[str], xpath: Optional[str], x: Optional[int], y: Optional[int]) -> Dict[str, Any]:
        script = self._build_scroll_script(selector, xpath, x, y)
        await self.client.send_command("Runtime.evaluate", { "expression": script, "returnByValue": True })
        
        return { "scrolled_x": x, "scrolled_y": y }

    async def evaluate(self, expression: str) -> Any:
        result = await self.client.send_command("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
            "awaitPromise": True,
        })

        if "exceptionDetails" in result:
            raise RuntimeError(f"JavaScript error: { result['exceptionDetails'] }")

        return result.get("result", {}).get("value")

    # ---- State ----

    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        result = await self.client.send_command("Network.getCookies", { "urls": urls } if urls else {})
        return result.get("cookies", [])

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        await self.client.send_command("Network.setCookies", {"cookies": cookies})
        return { "set": len(cookies) }

    # ---- Lifecycle ----

    async def close(self) -> None:
        await self.client.close()

    # ---- Internal helpers ----

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
        target_script = self._build_query_target_script(selector, xpath)
        script = f"""(function() {{
            const element = {target_script};
            if (!element) return null;
            const r = element.getBoundingClientRect();
            return {{x: r.left, y: r.top, width: r.width, height: r.height}};
        }})()"""

        result = await self.client.send_command("Runtime.evaluate", {
            "expression": script, "returnByValue": True
        })
        return result.get("result", {}).get("value")

    def _build_query_target_script(self, selector: Optional[str], xpath: Optional[str]) -> str:
        if selector:
            return f"document.querySelector({repr(selector)})"

        if xpath:
            return f"""document.evaluate(
                {repr(xpath)}, document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue"""

        raise ValueError("Either 'selector' or 'xpath' must be provided.")

    def _build_wait_condition_script(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str
    ) -> str:
        target_script = self._build_query_target_script(selector, xpath)

        if condition == "present":
            return f"!!({target_script})"

        if condition == "visible":
            return f"""(function() {{
                const element = {target_script};
                if (!element) return false;
                const s = window.getComputedStyle(element);
                return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            }})()"""

        if condition == "hidden":
            return f"""(function() {{
                const element = {target_script};
                if (!element) return true;
                const s = window.getComputedStyle(element);
                return s.display === 'none' || s.visibility === 'hidden' || s.opacity === '0';
            }})()"""

        raise ValueError(f"Unsupported condition: '{condition}'.")

    def _build_extract_map_function(self, extract_mode: str, attribute: Optional[str]) -> str:
        if extract_mode == "text":
            return "element => element.innerText || element.textContent || ''"

        if extract_mode == "html":
            return "element => element.outerHTML"

        if extract_mode == "attribute":
            return f"element => element.getAttribute({repr(attribute)})"

        raise ValueError(f"Unsupported extract_mode: '{extract_mode}'.")

    def _build_get_elements_script(self, selector: Optional[str], xpath: Optional[str], multiple: bool) -> str:
        if selector:
            if multiple:
                return f"Array.from(document.querySelectorAll({repr(selector)}))"
            return f"[document.querySelector({repr(selector)})].filter(Boolean)"

        if xpath:
            if multiple:
                return f"""(function() {{
                    const r = document.evaluate({repr(xpath)}, document, null,
                        XPathResult.ORDERED_NODE_SNAPSHOT_TYPE, null);
                    return Array.from({{length: r.snapshotLength}}, (_, i) => r.snapshotItem(i));
                }})()"""
            return f"""[document.evaluate(
                {repr(xpath)}, document, null,
                XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue].filter(Boolean)"""

        raise ValueError("Either 'selector' or 'xpath' must be provided.")

    def _build_extract_script(
        self, selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> str:
        get_elements = self._build_get_elements_script(selector, xpath, multiple)
        map_function = self._build_extract_map_function(extract_mode, attribute)

        if multiple:
            return f"({get_elements}).map({map_function})"

        return f"""(function() {{
            const elements = {get_elements};
            return elements.length ? elements.map({map_function})[0] : null;
        }})()"""

    def _build_scroll_script(self, selector: Optional[str], xpath: Optional[str], x: Optional[int], y: Optional[int]) -> str:
        if selector is not None or xpath is not None:
            target_script = self._build_query_target_script(selector, xpath)

            if x is not None or y is not None:
                return f"""(function() {{
                    const element = {target_script};
                    if (element) element.scrollBy({x or 0}, {y or 0});
                }})()"""

            return f"""(function() {{
                const element = {target_script};
                if (element) element.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }})()"""

        return f"window.scrollBy({x or 0}, {y or 0})"

@register_web_browser_service(WebBrowserDriver.CHROME)
class ChromeWebBrowserService(WebBrowserService):
    def __init__(self, id: str, config: Any, daemon: bool):
        super().__init__(id, config, daemon)
        debugger = config.debugger
        self._url: str = debugger.url or f"{debugger.protocol}://{debugger.host}:{debugger.port}"
        self._target_ids: List[str] = []

    async def create_session(self) -> ChromeBrowserSession:
        client, target_id = await CdpClient.create_tab(self._url)
        self._target_ids.append(target_id)

        return ChromeBrowserSession(client)

    async def close_browser(self) -> None:
        for target_id in self._target_ids:
            try:
                await CdpClient.close_tab(self._url, target_id)
            except Exception:
                pass

        self._target_ids.clear()
