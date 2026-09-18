from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from ..common import CommonTextEmbeddingModelComponentConfig
from .common import TextEmbeddingModelFamily
from ....common import ModelDriverType

class CustomTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: TextEmbeddingModelFamily = Field(..., description="Model family selecting the custom text embedding implementation.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this text embedding component exposes to workflows.")
