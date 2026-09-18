from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OxipngImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriverType

class OxipngImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriverType.OXIPNG]
    actions: List[OxipngImageCompressorActionConfig] = Field(default_factory=list)
