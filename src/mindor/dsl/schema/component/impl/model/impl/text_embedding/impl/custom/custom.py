from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from ..common import CommonTextEmbeddingModelComponentConfig
from ....common import ModelDriver

class CustomTextEmbeddingModelFamily(str, Enum):
    pass

class CustomTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomTextEmbeddingModelFamily = Field(..., description="Model family.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
