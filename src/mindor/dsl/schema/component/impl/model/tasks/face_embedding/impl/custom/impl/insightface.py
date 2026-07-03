from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import InsightfaceFaceEmbeddingModelActionConfig
from ...common import CommonFaceEmbeddingModelComponentConfig
from .common import FaceEmbeddingModelFamily
from .....common import ModelDriver

class InsightfaceFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceEmbeddingModelFamily.INSIGHTFACE]
    actions: List[InsightfaceFaceEmbeddingModelActionConfig] = Field(default_factory=list)
