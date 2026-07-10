from typing import Literal, Optional, List, Dict, Any
from pydantic import Field, model_validator
from mindor.dsl.schema.action import WebBrowserActionConfig
from .common import CommonWebBrowserComponentConfig, WebBrowserDriver

class PlaywrightWebBrowserComponentConfig(CommonWebBrowserComponentConfig):
    driver: Literal[WebBrowserDriver.PLAYWRIGHT]
    browser: Literal[ "chromium", "firefox", "webkit" ] = Field(default="chromium", description="Browser engine.")
    channel: Optional[str] = Field(default=None, description="System browser channel (e.g. 'chrome', 'msedge'). Chromium only.")
    headless: bool = Field(default=True, description="Run headless.")
    args: List[str] = Field(default_factory=list, description="CLI arguments passed to the browser process.")
    persistent_dir: Optional[str] = Field(default=None, description="Persistent profile directory.")
    cdp_url: Optional[str] = Field(default=None, description="Attach to a running Chromium over CDP (e.g. 'http://localhost:9222').")
    actions: List[WebBrowserActionConfig] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_channel_with_browser(self):
        if self.channel is not None and self.browser != "chromium":
            raise ValueError("'channel' can only be used with browser='chromium'.")
        return self

    @model_validator(mode="after")
    def validate_cdp_url_with_browser(self):
        if self.cdp_url is not None and self.browser != "chromium":
            raise ValueError("'cdp_url' can only be used with browser='chromium'.")
        return self

    @model_validator(mode="before")
    def validate_cdp_url_conflicts(cls, values: Dict[str, Any]):
        if values.get("cdp_url") is not None:
            conflicts = [ key for key in ("channel", "headless", "args", "persistent_dir") if key in values ]
            if conflicts:
                raise ValueError(f"When 'cdp_url' is set, these fields must not be specified: {', '.join(conflicts)}.")
        return values
