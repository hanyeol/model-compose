from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.dsl.schema.action import ActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.logger import logging
from ...context import ComponentActionContext
from .drivers.common import WebBrowserAction
import asyncio

if TYPE_CHECKING:
    from .drivers.common import WebBrowserSession

_DEFAULT_SESSION_KEY = "__default__"

class WebBrowserService(AsyncService):
    def __init__(self, id: str, config: WebBrowserComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: WebBrowserComponentConfig = config

        self._sessions: Dict[str, WebBrowserSession] = {}
        self._sessions_lock: asyncio.Lock = asyncio.Lock()

    async def run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        session = await self._acquire_session(action, context)
        timeout = self.config.timeout

        return await WebBrowserAction(action, timeout).run(context, session)

    async def _stop(self) -> None:
        async with self._sessions_lock:
            for session_key, session in self._sessions.items():
                try:
                    await session.close()
                except Exception:
                    logging.warning("Failed to close web-browser session '%s' for component '%s'", session_key, self.id)
            self._sessions.clear()
        await self._close_browser()

        await super()._stop()

    @abstractmethod
    async def _create_session(self) -> WebBrowserSession:
        pass

    async def _close_browser(self) -> None:
        """Release browser-level resources. Override in drivers that manage a browser process (e.g. Playwright)."""
        pass

    async def _acquire_session(self, action: ActionConfig, context: ComponentActionContext) -> WebBrowserSession:
        session_key = await self._resolve_session_key(action, context)

        if session_key not in self._sessions:
            async with self._sessions_lock:
                if session_key not in self._sessions:
                    logging.debug("Creating web-browser session '%s' for component '%s'", session_key, self.id)
                    self._sessions[session_key] = await self._create_session()

        return self._sessions[session_key]

    async def _resolve_session_key(self, action: ActionConfig, context: ComponentActionContext) -> str:
        if hasattr(action, "session_id") and action.session_id:
            return await context.render_variable(action.session_id)

        return _DEFAULT_SESSION_KEY

def register_web_browser_service(driver: WebBrowserDriver):
    def decorator(cls: Type[WebBrowserService]) -> Type[WebBrowserService]:
        WebBrowserServiceRegistry[driver] = cls
        return cls
    return decorator

WebBrowserServiceRegistry: Dict[WebBrowserDriver, Type[WebBrowserService]] = {}
