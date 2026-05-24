from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import InsightfaceFaceEmbeddingModelActionConfig
from ..common import CommonFaceEmbeddingModelComponentConfig
from .custom import CustomFaceEmbeddingModelFamily
from ....common import ModelDriver

class InsightfaceFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[CustomFaceEmbeddingModelFamily.INSIGHTFACE]
    actions: List[InsightfaceFaceEmbeddingModelActionConfig] = Field(default_factory=list)
