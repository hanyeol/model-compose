from typing import Union, Literal, Optional, Dict, List, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig
from .media import VideoAudioEncodingConfig

class WebBrowserActionMethod(str, Enum):
    NAVIGATE      = "navigate"
    WAIT_FOR      = "wait-for"
    EXTRACT       = "extract"
    SCREENSHOT    = "screenshot"
    CAPTURE_VIDEO = "capture-video"
    CLICK         = "click"
    INPUT_TEXT    = "input-text"
    SCROLL        = "scroll"
    EVALUATE      = "evaluate"
    GET_COOKIES   = "get-cookies"
    SET_COOKIES   = "set-cookies"

class CommonWebBrowserActionConfig(CommonActionConfig):
    method: WebBrowserActionMethod = Field(..., description="Browser operation this action performs.")
    session_id: Optional[str] = Field(default=None, description="Session identifier that isolates the browser tab used for this action.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for this browser action before failing (e.g., 10s).")

class WebBrowserNavigateActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.NAVIGATE]
    url: str = Field(..., description="Full URL to navigate the browser to.")
    wait_until: Union[Literal["load", "domcontentloaded", "networkidle", "commit"], str] = Field(default="load", description="Navigation event awaited before the action returns.")

class WebBrowserWaitForActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.WAIT_FOR]
    selector: Optional[str] = Field(default=None, description="CSS selector of the element to wait for. Mutually exclusive with `xpath`.")
    xpath: Optional[str] = Field(default=None, description="XPath of the element to wait for. Mutually exclusive with `selector`.")
    condition: Union[Literal["present", "visible", "hidden"], str] = Field(default="present", description="Element condition the wait resolves on.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

class WebBrowserExtractActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.EXTRACT]
    selector: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="CSS selector or selectors identifying elements to extract. Mutually exclusive with `xpath`.")
    xpath: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="XPath expression or expressions identifying elements to extract. Mutually exclusive with `selector`.")
    extract_mode: Union[Literal["text", "html", "attribute"], str] = Field(default="text", description="What to extract from matched elements.")
    attribute: Optional[str] = Field(default=None, description="Attribute name to extract. Required when `extract_mode` is `attribute`.")
    multiple: Union[bool, str] = Field(default=False, description="Whether to return all matches as a list rather than the first match.")

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

class WebBrowserScreenshotActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCREENSHOT]
    full_page: Union[bool, str] = Field(default=False, description="Whether the screenshot captures the full scrollable page.")
    selector: Optional[str] = Field(default=None, description="CSS selector limiting the screenshot to a specific element.")
    format: Union[Literal[ "png", "jpeg" ], str] = Field(default="png", description="Image format of the screenshot output.")
    quality: Optional[Union[int, str]] = Field(default=None, description="JPEG quality from 0 to 100. Applies only when `format` is `jpeg`.")

class WebBrowserCaptureVideoActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.CAPTURE_VIDEO]
    url: Optional[str] = Field(default=None, description="URL navigated to before capturing; when omitted, captures the current page.")
    selector: Optional[str] = Field(default=None, description="CSS selector of the <video> element to capture.")
    include_video_track: Union[bool, str] = Field(default=True, description="Whether the video track is included in the capture.")
    include_audio_track: Union[bool, str] = Field(default=True, description="Whether the audio track is included in the capture.")
    encoding: Optional[VideoAudioEncodingConfig] = Field(default=None, description="Encoding settings applied to the captured video and audio.")
    duration: Optional[Union[str, int, float]] = Field(default=None, description="Total capture duration; when unset, capture runs until stopped.")

class WebBrowserClickActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.CLICK]
    selector: Optional[str] = Field(default=None, description="CSS selector of the element to click.")
    xpath: Optional[str] = Field(default=None, description="XPath of the element to click.")
    x: Optional[Union[int, str]] = Field(default=None, description="Absolute X coordinate for a direct mouse click. Pair with `y`.")
    y: Optional[Union[int, str]] = Field(default=None, description="Absolute Y coordinate for a direct mouse click. Pair with `x`.")

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
    selector: Optional[str] = Field(default=None, description="CSS selector of the target input. Mutually exclusive with `xpath`.")
    xpath: Optional[str] = Field(default=None, description="XPath of the target input. Mutually exclusive with `selector`.")
    text: str = Field(..., description="Text typed into the target element.")
    clear_first: Union[bool, str] = Field(default=True, description="Whether existing content is cleared before typing.")

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

class WebBrowserScrollActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCROLL]
    selector: Optional[str] = Field(default=None, description="CSS selector of the element scrolled into view. Mutually exclusive with `xpath`.")
    xpath: Optional[str] = Field(default=None, description="XPath of the element scrolled into view. Mutually exclusive with `selector`.")
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
    expression: str = Field(..., description="JavaScript expression evaluated in the page context.")

class WebBrowserGetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.GET_COOKIES]
    urls: Optional[List[str]] = Field(default=None, description="URLs whose cookies are returned; when omitted, all cookies are returned.")

class WebBrowserSetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SET_COOKIES]
    cookies: List[Dict[str, Any]] = Field(..., description="Cookies to set on the browser session (each with name, value, domain, path, etc.).")

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
