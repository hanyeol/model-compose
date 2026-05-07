from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import WebBrowserActionConfig
from .common import CommonWebBrowserComponentConfig, WebBrowserDriver

class PlaywrightWebBrowserComponentConfig(CommonWebBrowserComponentConfig):
    driver: Literal[WebBrowserDriver.PLAYWRIGHT]
    browser: Literal[ "chromium", "firefox", "webkit" ] = Field(default="chromium", description="Browser engine to launch.")
    headless: bool = Field(default=True, description="Whether to run the browser in headless mode.")
    args: List[str] = Field(default_factory=list, description="Additional command-line arguments passed to the browser process.")
    actions: List[WebBrowserActionConfig] = Field(default_factory=list)
