from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import HtmlFrameRendererActionConfig
from .common import CommonHtmlFrameRendererComponentConfig, HtmlFrameRendererDriver

class PlaywrightHtmlFrameRendererComponentConfig(CommonHtmlFrameRendererComponentConfig):
    driver: Literal[HtmlFrameRendererDriver.PLAYWRIGHT]
    headless: bool = Field(default=True, description="Whether to run the browser in headless mode.")
    actions: List[HtmlFrameRendererActionConfig] = Field(default_factory=list)
