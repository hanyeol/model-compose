from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ImageBackgroundRemovalModelActionConfig
from .common import CommonImageBackgroundRemovalModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceImageBackgroundRemovalModelArchitecture(str, Enum):
    AUTO = "auto"

class HuggingfaceImageBackgroundRemovalModelComponentConfig(CommonImageBackgroundRemovalModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceImageBackgroundRemovalModelArchitecture = Field(default=HuggingfaceImageBackgroundRemovalModelArchitecture.AUTO, description="Model architecture family; \"auto\" infers from the model config.")
    actions: List[ImageBackgroundRemovalModelActionConfig] = Field(default_factory=list, description="Actions this image background removal component exposes to workflows.")
