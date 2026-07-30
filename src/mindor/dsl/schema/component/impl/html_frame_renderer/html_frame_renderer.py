from typing import Union, Dict, Annotated, Any
from pydantic import Field
from ..common import ComponentType, component_validator
from .impl import *

HtmlFrameRendererComponentConfig = Annotated[
    Union[
        PlaywrightHtmlFrameRendererComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.HTML_FRAME_RENDERER, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> None:
    if "driver" not in values:
        values["driver"] = HtmlFrameRendererDriver.PLAYWRIGHT
