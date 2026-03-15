from typing import Optional, Dict, List, Any
from mindor.dsl.schema.component import WebBrowserComponentConfig
from mindor.dsl.schema.action import ActionConfig, WebBrowserActionConfig, WebBrowserActionMethod
from mindor.core.utils.cdp_client import CdpClient
from mindor.core.utils.time import parse_duration
from ..base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ..context import ComponentActionContext
import asyncio

class WebBrowserSession:
    """
    High-level browser actions over a persistent CDP connection.
    The session lives as long as the component, preserving cookies/login state across actions.
    """

    def __init__(self, client: CdpClient):
        self.client = client
        self._lifecycle_enabled = False

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

    async def click(self, selector: Optional[str], xpath: Optional[str],
                    x: Optional[int], y: Optional[int], timeout: float) -> Dict[str, Any]:
        if x is not None and y is not None:
            cx, cy = int(x), int(y)
        else:
            cx, cy = await self._get_element_center(selector, xpath, timeout)

        for event_type in ("mousePressed", "mouseReleased"):
            await self.client.send_command("Input.dispatchMouseEvent", {
                "type": event_type, "x": cx, "y": cy, "button": "left", "clickCount": 1
            })

        return {"x": cx, "y": cy}

    async def input_text(self, selector: Optional[str], xpath: Optional[str],
                         text: str, clear_first: bool, timeout: float) -> Dict[str, Any]:
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

        return {"typed": text}

    async def screenshot(self, full_page: bool, selector: Optional[str],
                         fmt: str, quality: Optional[int]) -> str:
        params: Dict[str, Any] = {"format": fmt}
        if fmt == "jpeg" and quality is not None:
            params["quality"] = int(quality)
        if full_page:
            params["captureBeyondViewport"] = True
        if selector:
            box = await self._find_element_bounding_box(selector, None)
            if box:
                params["clip"] = {**box, "scale": 1}

        result = await self.client.send_command("Page.captureScreenshot", params)
        return result["data"]  # base64-encoded

    async def evaluate(self, expression: str, await_promise: bool) -> Any:
        params: Dict[str, Any] = {
            "expression": expression,
            "returnByValue": True,
        }
        if await_promise:
            params["awaitPromise"] = True

        result = await self.client.send_command("Runtime.evaluate", params)

        if "exceptionDetails" in result:
            raise RuntimeError(f"JavaScript error: {result['exceptionDetails']}")

        return result.get("result", {}).get("value")

    async def wait_for(self, selector: Optional[str], xpath: Optional[str],
                       condition: str, timeout: float) -> Dict[str, Any]:
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

    async def extract(self, selector: Optional[str], xpath: Optional[str],
                      extract_mode: str, attribute: Optional[str], multiple: bool) -> Any:
        js = self._build_extract_js(selector, xpath, extract_mode, attribute, multiple)
        result = await self.client.send_command("Runtime.evaluate", {
            "expression": js, "returnByValue": True
        })
        if "exceptionDetails" in result:
            raise RuntimeError(f"Extract JavaScript error: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        params = {}
        if urls:
            params["urls"] = urls
        result = await self.client.send_command("Network.getCookies", params)
        return result.get("cookies", [])

    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        await self.client.send_command("Network.setCookies", {"cookies": cookies})
        return {"set": len(cookies)}

    async def scroll(self, selector: Optional[str], x: int, y: int) -> Dict[str, Any]:
        if selector:
            js = f"""(function() {{
                const el = document.querySelector({repr(selector)});
                if (el) el.scrollBy({x}, {y});
            }})()"""
        else:
            js = f"window.scrollBy({x}, {y})"

        await self.client.send_command("Runtime.evaluate", {"expression": js, "returnByValue": True})
        return {"scrolled_x": x, "scrolled_y": y}

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

class WebBrowserAction:
    def __init__(self, config: WebBrowserActionConfig, timeout: Optional[str]):
        self.config: WebBrowserActionConfig = config
        self.timeout = timeout

    async def run(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        timeout = parse_duration((await context.render_variable(self.config.timeout) if self.config.timeout else self.timeout) or 30.0).total_seconds()

        result = await self._dispatch(context, session, timeout)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output, ignore_files=True)) if self.config.output else result

    async def _dispatch(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        if self.config.method == WebBrowserActionMethod.NAVIGATE:
            return await self._navigate(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.CLICK:
            return await self._click(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.INPUT_TEXT:
            return await self._input_text(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.SCREENSHOT:
            return await self._screenshot(context, session)

        if self.config.method == WebBrowserActionMethod.EVALUATE:
            return await self._evaluate(context, session)

        if self.config.method == WebBrowserActionMethod.WAIT_FOR:
            return await self._wait_for(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.EXTRACT:
            return await self._extract(context, session)

        if self.config.method == WebBrowserActionMethod.GET_COOKIES:
            return await self._get_cookies(context, session)

        if self.config.method == WebBrowserActionMethod.SET_COOKIES:
            return await self._set_cookies(context, session)

        if self.config.method == WebBrowserActionMethod.SCROLL:
            return await self._scroll(context, session)

        raise ValueError(f"Unsupported web-browser action method: {self.config.method}")

    async def _navigate(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        url        = await context.render_variable(self.config.url)
        wait_until = await context.render_variable(self.config.wait_until)

        return await session.navigate(url, wait_until, timeout)

    async def _click(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
        x        = await context.render_variable(self.config.x) if self.config.x is not None else None
        y        = await context.render_variable(self.config.y) if self.config.y is not None else None

        return await session.click(selector, xpath, x, y, timeout)

    async def _input_text(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector    = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath       = await context.render_variable(self.config.xpath) if self.config.xpath else None
        text        = await context.render_variable(self.config.text)
        clear_first = await context.render_variable(self.config.clear_first)

        return await session.input_text(selector, xpath, text, bool(clear_first), timeout)

    async def _screenshot(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        full_page = await context.render_variable(self.config.full_page)
        selector  = await context.render_variable(self.config.selector) if self.config.selector else None
        format    = await context.render_variable(self.config.format)
        quality   = await context.render_variable(self.config.quality) if self.config.quality is not None else None

        return await session.screenshot(bool(full_page), selector, format, quality)

    async def _evaluate(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        expression    = await context.render_variable(self.config.expression)
        await_promise = await context.render_variable(self.config.await_promise)

        return await session.evaluate(expression, bool(await_promise))

    async def _wait_for(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector  = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath     = await context.render_variable(self.config.xpath) if self.config.xpath else None
        condition = await context.render_variable(self.config.condition)

        return await session.wait_for(selector, xpath, condition, timeout)

    async def _extract(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        selector     = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath        = await context.render_variable(self.config.xpath) if self.config.xpath else None
        extract_mode = await context.render_variable(self.config.extract_mode)
        attribute    = await context.render_variable(self.config.attribute) if self.config.attribute else None
        multiple     = await context.render_variable(self.config.multiple)

        return await session.extract(selector, xpath, extract_mode, attribute, bool(multiple))

    async def _get_cookies(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        urls = await context.render_variable(self.config.urls) if self.config.urls else None

        return await session.get_cookies(urls)

    async def _set_cookies(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        cookies = await context.render_variable(self.config.cookies)

        return await session.set_cookies(cookies)

    async def _scroll(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        selector = await context.render_variable(self.config.selector) if self.config.selector else None
        x        = await context.render_variable(self.config.x)
        y        = await context.render_variable(self.config.y)

        return await session.scroll(selector, x, y)

@register_component(ComponentType.WEB_BROWSER)
class WebBrowserComponent(ComponentService):
    def __init__(self, id: str, config: WebBrowserComponentConfig, global_configs: ComponentGlobalConfigs, daemon: bool):
        super().__init__(id, config, global_configs, daemon)

        self.session: Optional[WebBrowserSession] = None

    async def _start(self) -> None:
        timeout_secs = parse_duration(self.config.timeout).total_seconds()
        client = await self._create_cdp_client(timeout_secs)
        self.session = WebBrowserSession(client)
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        if self.session:
            await self.session.client.close()
            self.session = None

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await WebBrowserAction(action, self.config.timeout).run(context, self.session)

    async def _create_cdp_client(self, timeout: float) -> CdpClient:
        if self.config.cdp_endpoint:
            client = CdpClient(self.config.cdp_endpoint, timeout=timeout)
            await client.connect()
            return client
        return await CdpClient.from_host_port(
            self.config.host, self.config.port,
            self.config.target_index, timeout=timeout
        )
