from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from .common import CommonImageAnalyzerComponentConfig, ImageAnalyzerDriverType

class NativeImageAnalyzerComponentConfig(CommonImageAnalyzerComponentConfig):
    driver: Literal[ImageAnalyzerDriverType.NATIVE]
    actions: List[ImageAnalyzerActionConfig] = Field(default_factory=list)
