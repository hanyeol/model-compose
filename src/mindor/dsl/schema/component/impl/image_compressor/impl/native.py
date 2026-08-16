from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriver

class NativeImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriver.NATIVE]
    actions: List[NativeImageCompressorActionConfig] = Field(default_factory=list)
