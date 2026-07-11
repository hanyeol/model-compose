from typing import Optional, Dict, Any
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.dsl.schema.action import ActionConfig
from mindor.core.logger import logging
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import WebBrowserService, WebBrowserServiceRegistry
from .drivers.common import WebBrowserAction, WebBrowserSession
import asyncio, importlib

_DEFAULT_SESSION_KEY = "__default__"

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
            if driver not in WebBrowserServiceRegistry:
                _load_driver_module(driver)
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
        session     = await self._acquire_session(session_key)

        return await WebBrowserAction(action, self.config.timeout).run(context, session)

    async def _resolve_session_key(self, action: ActionConfig, context: ComponentActionContext) -> str:
        if hasattr(action, "session_id") and action.session_id:
            return await context.render_variable(action.session_id)

        return _DEFAULT_SESSION_KEY

    async def _acquire_session(self, session_key: str) -> WebBrowserSession:
        if session_key not in self._sessions:
            async with self._sessions_lock:
                if session_key not in self._sessions:
                    logging.debug("Creating web-browser session '%s' for component '%s'", session_key, self.id)
                    self._sessions[session_key] = await self.service.create_session()

        return self._sessions[session_key]

def _load_driver_module(driver: WebBrowserDriver) -> None:
    """Import the module that registers the given web browser driver.

    Convention: a driver "foo-bar" (WebBrowserDriver.value) maps to
    mindor.core.component.services.web_browser.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_web_browser_service decorator,
    populating WebBrowserServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.web_browser.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported web browser driver: {driver}") from e
