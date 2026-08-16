from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OxipngImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriver

class OxipngImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriver.OXIPNG]
    actions: List[OxipngImageCompressorActionConfig] = Field(default_factory=list)
