from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class WebScraperSubmitConfig(BaseModel):
    """Form submission configuration."""
    selector: Optional[str] = Field(default=None, description="CSS selector to locate form or submit button")
    xpath: Optional[str] = Field(default=None, description="XPath expression to locate form or submit button")
    form: Optional[Dict[str, Any]] = Field(default=None, description="Form input values to fill. Keys are input selectors, values are input values")
    wait_for: Optional[str] = Field(default=None, description="CSS selector to wait for after form submission")

    @model_validator(mode="after")
    def validate_selector_or_xpath(self):
        if self.selector and self.xpath:
            raise ValueError("Cannot specify both 'selector' and 'xpath' in submit config")
        return self

class WebScraperActionConfig(CommonActionConfig):
    url: str = Field(..., description="URL to scrape")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers to include in the request")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Cookies to include in the request")
    selector: Optional[str] = Field(default=None, description="CSS selector to extract elements")
    xpath: Optional[str] = Field(default=None, description="XPath expression to extract elements")
    extract_mode: Union[Literal[ "text", "html", "attribute" ], str] = Field(default="text", description="Extraction mode")
    attribute: Optional[str] = Field(default=None, description="Attribute name to extract when extract_mode='attribute'")
    multiple: Union[bool, str] = Field(default=False, description="Extract multiple elements (returns list) or single element")
    enable_javascript: Union[bool, str] = Field(default=False, description="Enable JavaScript rendering (requires playwright)")
    wait_for: Optional[str] = Field(default=None, description="CSS selector to wait for when enable_javascript=true")
    timeout: Optional[str] = Field(default=None, description="Maximum time to wait for request completion")
    submit: Optional[WebScraperSubmitConfig] = Field(default=None, description="Form submission configuration. If specified, form is submitted before extraction")

    @model_validator(mode="after")
    def validate_selector_or_xpath(self):
        if self.selector and self.xpath:
            raise ValueError("Cannot specify both 'selector' and 'xpath', choose one")
        return self

    @model_validator(mode="after")
    def validate_attribute(self):
        if self.extract_mode == "attribute" and not self.attribute:
            raise ValueError("'attribute' must be specified when extract_mode='attribute'")
        return self

    @model_validator(mode="after")
    def validate_wait_for(self):
        # Skip validation if enable_javascript is a variable expression
        if self.wait_for and self.enable_javascript is False:
            raise ValueError("'wait_for' can only be used when enable_javascript=true")
        return self

    @model_validator(mode="after")
    def validate_submit(self):
        # Skip validation if enable_javascript is a variable expression
        if self.submit and self.enable_javascript is False:
            raise ValueError("'submit' requires enable_javascript=true")
        return self
