from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.action import WebBrowserActionConfig
from .common import ComponentType, CommonComponentConfig


class WebBrowserComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.WEB_BROWSER]

    cdp_endpoint: Optional[str] = Field(
        default=None,
        description="Full WebSocket debugger URL (e.g. ws://localhost:9222/devtools/page/<id>). "
                    "If omitted, the component discovers a target automatically via host/port."
    )
    host: str = Field(
        default="localhost",
        description="Host where the Chrome DevTools remote debugging port is exposed."
    )
    port: int = Field(
        default=9222,
        description="Chrome remote debugging port."
    )
    target_index: int = Field(
        default=0,
        description="Index of the browser target to attach to when auto-discovering via host/port."
    )

    novnc_url: Optional[str] = Field(
        default=None,
        description="URL of the noVNC viewer for this browser session. "
                    "Included in interrupt metadata so humans know where to connect."
    )

    timeout: str = Field(
        default="30s",
        description="Default command timeout for all actions."
    )

    actions: List[WebBrowserActionConfig] = Field(default_factory=list)
