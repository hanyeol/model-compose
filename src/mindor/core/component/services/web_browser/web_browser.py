from typing import Optional, Dict, Any
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.dsl.schema.action import ActionConfig, WebBrowserActionConfig, WebBrowserActionMethod
from mindor.core.utils.time import parse_duration
from mindor.core.logger import logging
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import WebBrowserService, WebBrowserSession, WebBrowserServiceRegistry
import asyncio

_DEFAULT_SESSION_KEY = "__default__"

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
        # Navigation
        if self.config.method == WebBrowserActionMethod.NAVIGATE:
            return await self._navigate(context, session, timeout)

        # Query
        if self.config.method == WebBrowserActionMethod.WAIT_FOR:
            return await self._wait_for(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.SCREENSHOT:
            return await self._screenshot(context, session)

        if self.config.method == WebBrowserActionMethod.EXTRACT:
            return await self._extract(context, session)

        # Interaction
        if self.config.method == WebBrowserActionMethod.CLICK:
            return await self._click(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.INPUT_TEXT:
            return await self._input(context, session, timeout)

        if self.config.method == WebBrowserActionMethod.SCROLL:
            return await self._scroll(context, session)

        if self.config.method == WebBrowserActionMethod.EVALUATE:
            return await self._evaluate(context, session)

        # State
        if self.config.method == WebBrowserActionMethod.GET_COOKIES:
            return await self._get_cookies(context, session)

        if self.config.method == WebBrowserActionMethod.SET_COOKIES:
            return await self._set_cookies(context, session)

        raise ValueError(f"Unsupported web-browser action method: {self.config.method}")

    # ---- Navigation ----

    async def _navigate(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        url        = await context.render_variable(self.config.url)
        wait_until = await context.render_variable(self.config.wait_until)

        return await session.navigate(url, wait_until, timeout)

    # ---- Query ----

    async def _wait_for(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector  = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath     = await context.render_variable(self.config.xpath) if self.config.xpath else None
        condition = await context.render_variable(self.config.condition)

        return await session.wait_for(selector, xpath, condition, timeout)

    async def _screenshot(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        full_page = await context.render_variable(self.config.full_page)
        selector  = await context.render_variable(self.config.selector) if self.config.selector else None
        format    = await context.render_variable(self.config.format)
        quality   = await context.render_variable(self.config.quality) if self.config.quality is not None else None

        return await session.screenshot(bool(full_page), selector, format, quality)

    async def _extract(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        selector     = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath        = await context.render_variable(self.config.xpath) if self.config.xpath else None
        extract_mode = await context.render_variable(self.config.extract_mode)
        attribute    = await context.render_variable(self.config.attribute) if self.config.attribute else None
        multiple     = await context.render_variable(self.config.multiple)

        return await session.extract(selector, xpath, extract_mode, attribute, bool(multiple))

    # ---- Interaction ----

    async def _click(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
        x        = await context.render_variable(self.config.x) if self.config.x is not None else None
        y        = await context.render_variable(self.config.y) if self.config.y is not None else None

        return await session.click(selector, xpath, x, y, timeout)

    async def _input(self, context: ComponentActionContext, session: WebBrowserSession, timeout: float) -> Any:
        selector    = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath       = await context.render_variable(self.config.xpath) if self.config.xpath else None
        text        = await context.render_variable(self.config.text)
        clear_first = await context.render_variable(self.config.clear_first)

        return await session.input(selector, xpath, text, bool(clear_first), timeout)

    async def _scroll(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        selector = await context.render_variable(self.config.selector) if self.config.selector else None
        xpath    = await context.render_variable(self.config.xpath) if self.config.xpath else None
        x        = int(await context.render_variable(self.config.x)) if self.config.x is not None else None
        y        = int(await context.render_variable(self.config.y)) if self.config.y is not None else None

        return await session.scroll(selector, xpath, x, y)

    async def _evaluate(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        expression = await context.render_variable(self.config.expression)

        return await session.evaluate(expression)

    # ---- State ----

    async def _get_cookies(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        urls = await context.render_variable(self.config.urls) if self.config.urls else None

        return await session.get_cookies(urls)

    async def _set_cookies(self, context: ComponentActionContext, session: WebBrowserSession) -> Any:
        cookies = await context.render_variable(self.config.cookies)

        return await session.set_cookies(cookies)

@register_component(ComponentType.WEB_BROWSER)
class WebBrowserComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WebBrowserComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: WebBrowserService = self._create_service(self.config.driver)
        self._sessions: Dict[str, WebBrowserSession] = {}
        self._sessions_lock: asyncio.Lock = asyncio.Lock()

    def _create_service(self, driver: WebBrowserDriver) -> WebBrowserService:
        try:
            if not WebBrowserServiceRegistry:
                from . import drivers
            return WebBrowserServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported web browser driver: {driver}")

    async def _start(self) -> None:
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        async with self._sessions_lock:
            for session_key, session in self._sessions.items():
                try:
                    await session.close()
                except Exception:
                    logging.warning("Failed to close web-browser session '%s' for component '%s'", session_key, self.id)
            self._sessions.clear()
        await self.service.close_browser()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        session_key = await self._resolve_session_key(action, context)
        session     = await self._get_or_create_session(session_key)

        return await WebBrowserAction(action, self.config.timeout).run(context, session)

    async def _resolve_session_key(self, action: ActionConfig, context: ComponentActionContext) -> str:
        if hasattr(action, "session_id") and action.session_id:
            return await context.render_variable(action.session_id)

        return _DEFAULT_SESSION_KEY

    async def _get_or_create_session(self, session_key: str) -> WebBrowserSession:
        if session_key not in self._sessions:
            async with self._sessions_lock:
                if session_key not in self._sessions:
                    logging.debug("Creating web-browser session '%s' for component '%s'", session_key, self.id)
                    self._sessions[session_key] = await self.service.create_session()

        return self._sessions[session_key]
