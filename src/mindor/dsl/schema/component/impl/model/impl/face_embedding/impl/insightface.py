from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import InsightfaceFaceEmbeddingModelActionConfig
from .common import CommonFaceEmbeddingModelComponentConfig, FaceEmbeddingModelFamily

class InsightfaceFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    family: Literal[FaceEmbeddingModelFamily.INSIGHTFACE]
    actions: List[InsightfaceFaceEmbeddingModelActionConfig] = Field(default_factory=list)
