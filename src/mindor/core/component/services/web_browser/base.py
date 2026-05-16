from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.dsl.schema.action import WebBrowserActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class WebBrowserSession(ABC):
    """Abstract browser session exposing high-level browser actions."""

    # ---- Navigation ----

    @abstractmethod
    async def navigate(self, url: str, wait_until: str, timeout: float) -> Dict[str, Any]:
        pass

    # ---- Interaction ----

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

    # ---- Query ----

    @abstractmethod
    async def wait_for(
        self,
        selector: Optional[str],
        xpath: Optional[str],
        condition: str,
        timeout: float
    ) -> Dict[str, Any]:
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

    # ---- Capture ----

    @abstractmethod
    async def screenshot(
        self,
        full_page: bool,
        selector: Optional[str],
        format: str,
        quality: Optional[int]
    ) -> str:
        pass

    # ---- State ----

    @abstractmethod
    async def get_cookies(self, urls: Optional[List[str]]) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def set_cookies(self, cookies: List[Dict[str, Any]]) -> Dict[str, Any]:
        pass

    # ---- Lifecycle ----

    @abstractmethod
    async def close(self) -> None:
        pass

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
