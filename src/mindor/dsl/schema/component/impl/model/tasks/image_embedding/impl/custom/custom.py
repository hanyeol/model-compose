from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ImageEmbeddingModelActionConfig
from ..common import CommonImageEmbeddingModelComponentConfig
from .common import ImageEmbeddingModelFamily
from ....common import ModelDriver

class CustomImageEmbeddingModelComponentConfig(CommonImageEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ImageEmbeddingModelFamily = Field(..., description="Model family selecting the custom image embedding implementation.")
    actions: List[ImageEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this image embedding component exposes to workflows.")
