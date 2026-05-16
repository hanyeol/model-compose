from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, model_validator
from mindor.dsl.schema.action import WebBrowserActionConfig
from .common import CommonWebBrowserComponentConfig, WebBrowserDriver

class ChromeWebBrowserDebuggerConfig(BaseModel):
    url: Optional[str] = Field(default=None, description="Chrome DevTools URL (e.g. http://localhost:9222).")
    host: str = Field(default="localhost", description="Chrome DevTools hostname or IP address.")
    port: int = Field(default=9222, ge=1, le=65535, description="Chrome remote debugging port.")
    protocol: Literal["http", "https"] = Field(default="http", description="Connection protocol.")

    @model_validator(mode="before")
    @classmethod
    def validate_url_or_host(cls, values: Dict[str, Any]):
        if values.get("url") and values.get("host"):
            raise ValueError("Either 'url' or 'host' should be set, but not both.")
        return values

class ChromeWebBrowserComponentConfig(CommonWebBrowserComponentConfig):
    driver: Literal[WebBrowserDriver.CHROME] = WebBrowserDriver.CHROME
    debugger: ChromeWebBrowserDebuggerConfig = Field(default_factory=ChromeWebBrowserDebuggerConfig, description="Chrome DevTools debugger connection settings.")
    actions: List[WebBrowserActionConfig] = Field(default_factory=list)
