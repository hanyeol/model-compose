from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Dict
from abc import abstractmethod
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

if TYPE_CHECKING:
    from .drivers.common import WebBrowserSession

class WebBrowserService(AsyncService):
    def __init__(self, id: str, config: WebBrowserComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: WebBrowserComponentConfig = config

    @abstractmethod
    async def create_session(self) -> WebBrowserSession:
        pass

    async def close_browser(self) -> None:
        """Release browser-level resources. Override in drivers that manage a browser process (e.g. Playwright)."""
        pass

def register_web_browser_service(driver: WebBrowserDriver):
    def decorator(cls: Type[WebBrowserService]) -> Type[WebBrowserService]:
        WebBrowserServiceRegistry[driver] = cls
        return cls
    return decorator

WebBrowserServiceRegistry: Dict[WebBrowserDriver, Type[WebBrowserService]] = {}
