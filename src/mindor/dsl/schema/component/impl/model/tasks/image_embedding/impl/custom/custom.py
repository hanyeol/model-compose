from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageEmbeddingModelActionConfig
from ..common import CommonImageEmbeddingModelComponentConfig
from .impl.common import ImageEmbeddingModelFamily
from ....common import ModelDriver

class CustomImageEmbeddingModelComponentConfig(CommonImageEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ImageEmbeddingModelFamily = Field(..., description="Model family.")
    actions: List[ImageEmbeddingModelActionConfig] = Field(default_factory=list)
