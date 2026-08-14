from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class HtmlFrameRendererDriver(str, Enum):
    PLAYWRIGHT = "playwright"

class CommonHtmlFrameRendererComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.HTML_FRAME_RENDERER]
    driver: HtmlFrameRendererDriver = Field(..., description="Backend implementation used to render HTML frames.")
