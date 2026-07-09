from typing import Union, Literal, Optional, Dict, List, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class WebBrowserActionMethod(str, Enum):
    NAVIGATE      = "navigate"
    WAIT_FOR      = "wait-for"
    SCREENSHOT    = "screenshot"
    EXTRACT       = "extract"
    CLICK         = "click"
    INPUT_TEXT    = "input-text"
    SCROLL        = "scroll"
    EVALUATE      = "evaluate"
    GET_COOKIES   = "get-cookies"
    SET_COOKIES   = "set-cookies"
    CAPTURE_VIDEO = "capture-video"

class CommonWebBrowserActionConfig(CommonActionConfig):
    method: WebBrowserActionMethod = Field(..., description="Browser action method.")
    session_id: Optional[str] = Field(default=None, description="Session ID for tab isolation.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Per-action timeout override (e.g. '10s').")

class WebBrowserNavigateActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.NAVIGATE]
    url: str = Field(..., description="URL to navigate to.")
    wait_until: Union[Literal["load", "domcontentloaded", "networkidle", "commit"], str] = Field(default="load", description="Navigation event to wait for before returning.")

class WebBrowserWaitForActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.WAIT_FOR]
    selector: Optional[str] = Field(default=None, description="CSS selector to wait for.")
    xpath: Optional[str] = Field(default=None, description="XPath to wait for.")
    condition: Union[Literal["present", "visible", "hidden"], str] = Field(default="present", description="Condition to wait for.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

class WebBrowserScreenshotActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCREENSHOT]
    full_page: Union[bool, str] = Field(default=False, description="Capture the full scrollable page.")
    selector: Optional[str] = Field(default=None, description="CSS selector to capture only a specific element.")
    format: Union[Literal["png", "jpeg"], str] = Field(default="png", description="Image format.")
    quality: Optional[Union[int, str]] = Field(default=None, description="JPEG quality (0-100). Only applicable when format='jpeg'.")

class WebBrowserExtractActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.EXTRACT]
    selector: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="CSS selector(s) to extract elements.")
    xpath: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="XPath expression(s) to extract elements.")
    extract_mode: Union[Literal["text", "html", "attribute"], str] = Field(default="text", description="Extraction mode.")
    attribute: Optional[str] = Field(default=None, description="Attribute name when extract_mode='attribute'.")
    multiple: Union[bool, str] = Field(default=False, description="Return all matches as a list.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

    @model_validator(mode="after")
    def validate_attribute(self):
        if self.extract_mode == "attribute" and self.attribute is None:
            raise ValueError("'attribute' is required when extract_mode is 'attribute'.")
        return self

class WebBrowserClickActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.CLICK]
    selector: Optional[str] = Field(default=None, description="CSS selector of the element to click.")
    xpath: Optional[str] = Field(default=None, description="XPath of the element to click.")
    x: Optional[Union[int, str]] = Field(default=None, description="Absolute X coordinate for a direct mouse click.")
    y: Optional[Union[int, str]] = Field(default=None, description="Absolute Y coordinate for a direct mouse click.")

    @model_validator(mode="after")
    def validate_target(self):
        targets = sum([ self.selector is not None, self.xpath is not None, self.x is not None and self.y is not None ])
        if targets == 0:
            raise ValueError("One of 'selector', 'xpath', or coordinates('x' and 'y') must be provided.")
        if targets > 1:
            raise ValueError("Only one of 'selector', 'xpath', or coordinates('x' and 'y') can be provided.")
        return self

class WebBrowserInputTextActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.INPUT_TEXT]
    selector: Optional[str] = Field(default=None, description="CSS selector of the target input.")
    xpath: Optional[str] = Field(default=None, description="XPath of the target input.")
    text: str = Field(..., description="Text to type into the element.")
    clear_first: Union[bool, str] = Field(default=True, description="Clear existing content before typing.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

class WebBrowserScrollActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCROLL]
    selector: Optional[str] = Field(default=None, description="CSS selector of the target element.")
    xpath: Optional[str] = Field(default=None, description="XPath of the target element.")
    x: Optional[Union[int, str]] = Field(default=None, description="Horizontal scroll amount in pixels.")
    y: Optional[Union[int, str]] = Field(default=None, description="Vertical scroll amount in pixels.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        if self.selector is None and self.xpath is None and self.x is None and self.y is None:
            raise ValueError("At least one of 'selector', 'xpath', or coordinates('x' and 'y') must be provided.")
        return self

class WebBrowserEvaluateActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.EVALUATE]
    expression: str = Field(..., description="JavaScript expression to evaluate in the page context.")

class WebBrowserGetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.GET_COOKIES]
    urls: Optional[List[str]] = Field(default=None, description="Restrict returned cookies to these URLs. If omitted, returns all cookies.")

class WebBrowserSetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SET_COOKIES]
    cookies: List[Dict[str, Any]] = Field(..., description="List of cookie dicts (name, value, domain, path, ...).")

class WebBrowserCaptureVideoActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.CAPTURE_VIDEO]
    url: Optional[str] = Field(default=None, description="URL to navigate to before capturing. If omitted, captures the current page.")
    source: Union[Literal["tab", "window", "screen"], str] = Field(default="tab", description="Capture source for getDisplayMedia.")
    video: Union[bool, str] = Field(default=True, description="Capture the video track.")
    audio: Union[bool, str] = Field(default=True, description="Capture the audio track.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Video/audio encoding settings. If omitted, uses the browser default and enables hardware acceleration when available.")
    chunk_interval: Union[str, int, float] = Field(default="1s", description="Interval between emitted chunks (e.g. '1s', '500ms').")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration (e.g. '30s'). If omitted, capture continues until stopped.")

WebBrowserActionConfig = Annotated[
    Union[
        WebBrowserNavigateActionConfig,
        WebBrowserWaitForActionConfig,
        WebBrowserScreenshotActionConfig,
        WebBrowserExtractActionConfig,
        WebBrowserClickActionConfig,
        WebBrowserInputTextActionConfig,
        WebBrowserScrollActionConfig,
        WebBrowserEvaluateActionConfig,
        WebBrowserGetCookiesActionConfig,
        WebBrowserSetCookiesActionConfig,
        WebBrowserCaptureVideoActionConfig,
    ],
    Field(discriminator="method")
]
