from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceTextGenerationModelArchitecture(str, Enum):
    AUTO = "auto"

class HuggingfaceTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceTextGenerationModelArchitecture = Field(default=HuggingfaceTextGenerationModelArchitecture.AUTO, description="Model architecture family; \"auto\" infers from the model config.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list, description="Actions this text generation component exposes to workflows.")
