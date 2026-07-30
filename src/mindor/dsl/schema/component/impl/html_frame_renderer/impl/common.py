from typing import Literal, List, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, model_validator
from ...common import CommonComponentConfig, ComponentType

class HtmlFrameRendererDriver(str, Enum):
    PLAYWRIGHT = "playwright"

class HtmlFrameRendererHtmlConfig(BaseModel):
    name: str = Field(..., description="Identifier used by actions to reference this HTML entry.")
    source: str = Field(..., description="HTML source: http(s):// URL, file path, directory with index.html, or inline HTML.")

class CommonHtmlFrameRendererComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTML_FRAME_RENDERER]
    driver: HtmlFrameRendererDriver = Field(..., description="HTML frame renderer backend driver.")
    htmls: List[HtmlFrameRendererHtmlConfig] = Field(default_factory=list, description="HTML entries available to actions in this component.")

    @model_validator(mode="before")
    def inflate_single_html(cls, values: Dict[str, Any]):
        if "htmls" not in values:
            html = values.pop("html", None)
            if isinstance(html, str):
                html = { "name": "__default__", "source": html }
            values["htmls"] = [ html ]
        return values

    @model_validator(mode="after")
    def validate_html_references(self):
        names = { html.name for html in self.htmls }
        for action in self.actions:
            if action.html not in names:
                raise ValueError(f"Action references html '{action.html}' but no such entry in 'htmls'.")
        return self
