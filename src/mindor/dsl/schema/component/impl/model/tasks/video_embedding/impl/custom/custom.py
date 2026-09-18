from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import VideoEmbeddingModelActionConfig
from ..common import CommonVideoEmbeddingModelComponentConfig
from .common import VideoEmbeddingModelFamily
from ....common import ModelDriverType

class CustomVideoEmbeddingModelComponentConfig(CommonVideoEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: VideoEmbeddingModelFamily = Field(..., description="Model family selecting the custom video embedding implementation.")
    actions: List[VideoEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this video embedding component exposes to workflows.")
