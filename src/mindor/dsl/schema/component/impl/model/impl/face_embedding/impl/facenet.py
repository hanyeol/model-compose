from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FacenetFaceEmbeddingModelActionConfig
from .common import CommonFaceEmbeddingModelComponentConfig, FaceEmbeddingModelFamily

class FacenetFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    family: Literal[FaceEmbeddingModelFamily.FACENET]
    actions: List[FacenetFaceEmbeddingModelActionConfig] = Field(default_factory=list)
