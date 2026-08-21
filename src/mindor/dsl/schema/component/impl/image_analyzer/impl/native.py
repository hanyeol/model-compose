from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from .common import CommonImageAnalyzerComponentConfig, ImageAnalyzerDriver

class NativeImageAnalyzerComponentConfig(CommonImageAnalyzerComponentConfig):
    driver: Literal[ImageAnalyzerDriver.NATIVE]
    actions: List[ImageAnalyzerActionConfig] = Field(default_factory=list)
