from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvImageAnalyzerActionConfig
from .common import CommonImageAnalyzerComponentConfig, ImageAnalyzerDriverType

class OpenCvImageAnalyzerComponentConfig(CommonImageAnalyzerComponentConfig):
    driver: Literal[ImageAnalyzerDriverType.OPENCV]
    actions: List[OpenCvImageAnalyzerActionConfig] = Field(default_factory=list)
