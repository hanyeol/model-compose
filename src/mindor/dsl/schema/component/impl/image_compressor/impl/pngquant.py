from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import PngquantImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriver

class PngquantImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriver.PNGQUANT]
    actions: List[PngquantImageCompressorActionConfig] = Field(default_factory=list)
