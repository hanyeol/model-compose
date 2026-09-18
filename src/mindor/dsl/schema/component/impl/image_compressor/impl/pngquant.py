from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PngquantImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriverType

class PngquantImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriverType.PNGQUANT]
    actions: List[PngquantImageCompressorActionConfig] = Field(default_factory=list)
