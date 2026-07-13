from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageBackgroundRemovalModelActionConfig
from .common import CommonImageBackgroundRemovalModelComponentConfig
from ...common import ModelDriver

class HuggingfaceImageBackgroundRemovalModelArchitecture(str, Enum):
    AUTO = "auto"

class HuggingfaceImageBackgroundRemovalModelComponentConfig(CommonImageBackgroundRemovalModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceImageBackgroundRemovalModelArchitecture = Field(default=HuggingfaceImageBackgroundRemovalModelArchitecture.AUTO, description="Model architecture.")
    actions: List[ImageBackgroundRemovalModelActionConfig] = Field(default_factory=list)
