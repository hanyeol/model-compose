from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebBrowserActionConfig
from .common import CommonWebBrowserComponentConfig, WebBrowserDriver

class ChromeWebBrowserComponentConfig(CommonWebBrowserComponentConfig):
    driver: Literal[WebBrowserDriver.CHROME] = WebBrowserDriver.CHROME
    endpoint: Optional[str] = Field(default=None, description="Full WebSocket debugger URL (e.g. ws://localhost:9222/devtools/page/<id>). If omitted, auto-discovers via host/port.")
    host: str = Field(default="localhost", description="Host where the Chrome DevTools remote debugging port is exposed.")
    port: int = Field(default=9222, description="Chrome remote debugging port.")
    target_index: int = Field(default=0, description="Index of the browser target to attach to when auto-discovering via host/port.")
    actions: List[WebBrowserActionConfig] = Field(default_factory=list)
