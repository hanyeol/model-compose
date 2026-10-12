from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import OpenCvImageProcessorActionConfig
from .common import CommonImageProcessorComponentConfig, ImageProcessorDriverType

class OpenCvImageProcessorComponentConfig(CommonImageProcessorComponentConfig):
    driver: Literal[ImageProcessorDriverType.OPENCV]
    actions: List[OpenCvImageProcessorActionConfig] = Field(default_factory=list)
