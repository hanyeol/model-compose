from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class WebScraperSubmitConfig(BaseModel):
    selector: Optional[str] = Field(default=None, description="CSS selector locating the form or submit button. Mutually exclusive with `xpath`.")
    xpath: Optional[str] = Field(default=None, description="XPath locating the form or submit button. Mutually exclusive with `selector`.")
    form: Optional[Dict[str, Any]] = Field(default=None, description="Form field values to fill; keys are input selectors and values are input values.")
    wait_for: Optional[str] = Field(default=None, description="CSS selector awaited after form submission.")

    @model_validator(mode="after")
    def validate_selector_or_xpath(self):
        if self.selector and self.xpath:
            raise ValueError("Cannot specify both 'selector' and 'xpath' in submit config")
        return self

class WebScraperActionConfig(CommonActionConfig):
    url: Union[str, List[str]] = Field(..., description="URL or list of URLs to scrape.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input URLs processed per batch.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with the scrape request.")
    cookies: Dict[str, str] = Field(default_factory=dict, description="Cookies sent with the scrape request.")
    selector: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="CSS selector or selectors identifying elements to extract. Mutually exclusive with `xpath`.")
    xpath: Optional[Union[str, List[str], Dict[str, str]]] = Field(default=None, description="XPath expression or expressions identifying elements to extract. Mutually exclusive with `selector`.")
    extract_mode: Union[Literal[ "text", "html", "attribute" ], str] = Field(default="text", description="What to extract from matched elements.")
    attribute: Optional[str] = Field(default=None, description="Attribute name to extract. Required when `extract_mode` is `attribute`.")
    multiple: Union[bool, str] = Field(default=False, description="Whether to return all matches as a list rather than the first match.")
    enable_javascript: Union[bool, str] = Field(default=False, description="Whether pages are rendered with JavaScript enabled (requires Playwright).")
    wait_until: Union[Literal[ "load", "domcontentloaded", "networkidle", "commit" ], str] = Field(default="networkidle", description="Navigation event awaited before extraction begins.")
    wait_for: Optional[str] = Field(default=None, description="CSS selector awaited after navigation. Requires `enable_javascript` to be true.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for the scrape request to complete before failing.")
    submit: Optional[WebScraperSubmitConfig] = Field(default=None, description="Form submission performed before extraction. Requires `enable_javascript` to be true.")

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
