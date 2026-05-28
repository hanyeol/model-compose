from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from ..common import CommonTextEmbeddingModelComponentConfig
from .impl.common import TextEmbeddingModelFamily
from ....common import ModelDriver

class CustomTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: TextEmbeddingModelFamily = Field(..., description="Model family.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
