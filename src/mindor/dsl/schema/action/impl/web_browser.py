from typing import Union, Literal, Optional, Dict, List, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from .common import CommonActionConfig

class WebBrowserActionMethod(str, Enum):
    NAVIGATE    = "navigate"
    CLICK       = "click"
    INPUT_TEXT  = "input-text"
    SCREENSHOT  = "screenshot"
    EVALUATE    = "evaluate"
    WAIT_FOR    = "wait-for"
    EXTRACT     = "extract"
    GET_COOKIES = "get-cookies"
    SET_COOKIES = "set-cookies"
    SCROLL      = "scroll"

class CommonWebBrowserActionConfig(CommonActionConfig):
    method: WebBrowserActionMethod = Field(..., description="Browser action method.")
    timeout: Optional[str] = Field(default=None, description="Per-action timeout override (e.g. '10s'). Falls back to component-level timeout.")

class WebBrowserNavigateActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.NAVIGATE]
    url: str = Field(..., description="URL to navigate to.")
    wait_until: Union[Literal["load", "domcontentloaded", "networkidle"], str] = Field(
        default="load", description="Navigation event to wait for before returning."
    )

class WebBrowserClickActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.CLICK]
    selector: Optional[str] = Field(default=None, description="CSS selector of the element to click.")
    xpath: Optional[str] = Field(default=None, description="XPath of the element to click.")
    x: Optional[Union[int, str]] = Field(default=None, description="Absolute X coordinate for a direct mouse click.")
    y: Optional[Union[int, str]] = Field(default=None, description="Absolute Y coordinate for a direct mouse click.")

    @model_validator(mode="after")
    def validate_target(self):
        has_selector = self.selector is not None
        has_xpath = self.xpath is not None
        has_coords = self.x is not None and self.y is not None
        targets = [has_selector, has_xpath, has_coords]
        if sum(targets) != 1:
            raise ValueError("Exactly one of 'selector', 'xpath', or 'x'+'y' must be provided.")
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

class WebBrowserScreenshotActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCREENSHOT]
    full_page: Union[bool, str] = Field(default=False, description="Capture the full scrollable page.")
    selector: Optional[str] = Field(default=None, description="CSS selector to capture only a specific element.")
    format: Union[Literal["png", "jpeg"], str] = Field(default="png", description="Image format.")
    quality: Optional[Union[int, str]] = Field(default=None, description="JPEG quality (0-100). Only applicable when format='jpeg'.")

class WebBrowserEvaluateActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.EVALUATE]
    expression: str = Field(..., description="JavaScript expression to evaluate in the page context.")
    await_promise: Union[bool, str] = Field(default=False, description="Whether to await the result if the expression returns a Promise.")

class WebBrowserWaitForActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.WAIT_FOR]
    selector: Optional[str] = Field(default=None, description="CSS selector to wait for.")
    xpath: Optional[str] = Field(default=None, description="XPath to wait for.")
    condition: Union[Literal["present", "visible", "hidden"], str] = Field(
        default="present", description="Condition to wait for."
    )

    @model_validator(mode="after")
    def validate_target(self):
        if self.selector is None and self.xpath is None:
            raise ValueError("Either 'selector' or 'xpath' must be provided.")
        if self.selector is not None and self.xpath is not None:
            raise ValueError("Only one of 'selector' or 'xpath' can be provided.")
        return self

class WebBrowserExtractActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.EXTRACT]
    selector: Optional[str] = Field(default=None, description="CSS selector.")
    xpath: Optional[str] = Field(default=None, description="XPath expression.")
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

class WebBrowserGetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.GET_COOKIES]
    urls: Optional[List[str]] = Field(default=None, description="Restrict returned cookies to these URLs. If omitted, returns all cookies.")

class WebBrowserSetCookiesActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SET_COOKIES]
    cookies: List[Dict[str, Any]] = Field(..., description="List of cookie dicts (name, value, domain, path, ...).")

class WebBrowserScrollActionConfig(CommonWebBrowserActionConfig):
    method: Literal[WebBrowserActionMethod.SCROLL]
    selector: Optional[str] = Field(default=None, description="Scroll a specific element into view.")
    x: Union[int, str] = Field(default=0, description="Horizontal scroll amount in pixels.")
    y: Union[int, str] = Field(default=0, description="Vertical scroll amount in pixels.")

WebBrowserActionConfig = Annotated[
    Union[
        WebBrowserNavigateActionConfig,
        WebBrowserClickActionConfig,
        WebBrowserInputTextActionConfig,
        WebBrowserScreenshotActionConfig,
        WebBrowserEvaluateActionConfig,
        WebBrowserWaitForActionConfig,
        WebBrowserExtractActionConfig,
        WebBrowserGetCookiesActionConfig,
        WebBrowserSetCookiesActionConfig,
        WebBrowserScrollActionConfig,
    ],
    Field(discriminator="method")
]
