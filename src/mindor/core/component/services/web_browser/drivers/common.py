from __future__ import annotations

from typing import Optional, Dict, List, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.action import WebBrowserActionConfig, WebBrowserActionMethod
from mindor.core.utils.time import parse_duration
from ..base import ComponentActionContext

class WebBrowserSession(ABC):
    """Abstract browser session exposing high-level browser actions."""

    @abstractmethod
    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def click(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        x: Optional[int],
        y: Optional[int],
        timeout: float
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def input(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        text: str,
        clear_first: bool,
        timeout: float
    ) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def scroll(self, selector: Optional[str], xpath: Optional[str], x: Optional[int], y: Optional[int]) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> None:
        pass

    @abstractmethod
    async def extract(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        extract_mode: str,
        attribute: Optional[str],
        multiple: bool
    ) -> Any:
        pass

    @abstractmethod
    async def evaluate(self, expression: str) -> Any:
        pass

    @abstractmethod
    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> str:
        pass

    @abstractmethod
    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class WebBrowserAction:
    def __init__(self, config: WebBrowserActionConfig, timeout: Optional[str]):
        self.config: WebBrowserActionConfig = config
        self.timeout = timeout

    async def run(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        timeout = parse_duration((await context.render_variable(self.config.timeout) if self.config.timeout else self.timeout) or 30.0)

        result = await self._dispatch(context, self.config.method, session, timeout)
        context.register_source("result", result)

        return (await context.render_variable(self.config.output)) if self.config.output else result

    async def _dispatch(
        self,
        context: ComponentActionContext,
        method: WebBrowserActionMethod,
        session: WebBrowserSession,
        timeout: float,
    ) -> Any:
        # Navigation
        if method == WebBrowserActionMethod.NAVIGATE:
            url        = await context.render_variable(self.config.url)
            wait_until = await context.render_variable(self.config.wait_until)

            if url is None:
                raise ValueError("'url' must be specified for 'navigate' method")

            return await session.navigate(url, wait_until, timeout)

        # Query
        if method == WebBrowserActionMethod.WAIT_FOR:
            selector  = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath     = await context.render_variable(self.config.xpath) if self.config.xpath else None
            condition = await context.render_variable(self.config.condition)

            return await session.wait_for(selector, xpath, condition, timeout)

        if method == WebBrowserActionMethod.SCREENSHOT:
            selector  = await context.render_variable(self.config.selector) if self.config.selector else None
            full_page = bool(await context.render_variable(self.config.full_page))
            format    = await context.render_variable(self.config.format)
            quality   = await context.render_variable(self.config.quality) if self.config.quality is not None else None

            return await session.screenshot(full_page, selector, format, quality)

        if method == WebBrowserActionMethod.EXTRACT:
            selector     = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath        = await context.render_variable(self.config.xpath) if self.config.xpath else None
            extract_mode = await context.render_variable(self.config.extract_mode)
            attribute    = await context.render_variable(self.config.attribute) if self.config.attribute else None
            multiple     = bool(await context.render_variable(self.config.multiple))

            if selector:
                if isinstance(selector, dict):
                    return { key: await session.extract(expr, None, extract_mode, attribute, multiple) for key, expr in selector.items() }
                if isinstance(selector, list):
                    return [ await session.extract(expr, None, extract_mode, attribute, multiple) for expr in selector ]
                return await session.extract(selector, None, extract_mode, attribute, multiple)

            if xpath:
                if isinstance(xpath, dict):
                    return { key: await session.extract(None, expr, extract_mode, attribute, multiple) for key, expr in xpath.items() }
                if isinstance(xpath, list):
                    return [ await session.extract(None, expr, extract_mode, attribute, multiple) for expr in xpath ]
                return await session.extract(None, xpath, extract_mode, attribute, multiple)

            return await session.extract(None, None, extract_mode, attribute, multiple)

        # Interaction
        if method == WebBrowserActionMethod.CLICK:
            selector = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
            x        = await context.render_variable(self.config.x) if self.config.x is not None else None
            y        = await context.render_variable(self.config.y) if self.config.y is not None else None

            return await session.click(selector, xpath, x, y, timeout)

        if method == WebBrowserActionMethod.INPUT_TEXT:
            selector    = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath       = await context.render_variable(self.config.xpath) if self.config.xpath else None
            text        = await context.render_variable(self.config.text)
            clear_first = bool(await context.render_variable(self.config.clear_first))

            if text is None:
                raise ValueError("'text' must be specified for 'input-text' method")

            return await session.input(selector, xpath, text, clear_first, timeout)

        if method == WebBrowserActionMethod.SCROLL:
            selector = await context.render_variable(self.config.selector) if self.config.selector else None
            xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
            x        = int(await context.render_variable(self.config.x)) if self.config.x is not None else None
            y        = int(await context.render_variable(self.config.y)) if self.config.y is not None else None

            return await session.scroll(selector, xpath, x, y)

        if method == WebBrowserActionMethod.EVALUATE:
            expression = await context.render_variable(self.config.expression)

            if expression is None:
                raise ValueError("'expression' must be specified for 'evaluate' method")

            return await session.evaluate(expression)

        # State
        if method == WebBrowserActionMethod.GET_COOKIES:
            urls = await context.render_variable(self.config.urls) if self.config.urls else None

            return await session.get_cookies(urls)

        if method == WebBrowserActionMethod.SET_COOKIES:
            cookies = await context.render_variable(self.config.cookies)

            if cookies is None:
                raise ValueError("'cookies' must be specified for 'set-cookies' method")

            return await session.set_cookies(cookies)

        raise ValueError(f"Unsupported web-browser action method: {method}")
