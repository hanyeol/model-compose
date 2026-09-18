from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeImageCompressorActionConfig
from .common import CommonImageCompressorComponentConfig, ImageCompressorDriverType

class NativeImageCompressorComponentConfig(CommonImageCompressorComponentConfig):
    driver: Literal[ImageCompressorDriverType.NATIVE]
    actions: List[NativeImageCompressorActionConfig] = Field(default_factory=list)
