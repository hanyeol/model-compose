from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import DlibFaceEmbeddingModelActionConfig
from .common import CommonFaceEmbeddingModelComponentConfig, FaceEmbeddingModelFamily

class DlibFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    family: Literal[FaceEmbeddingModelFamily.DLIB]
    actions: List[DlibFaceEmbeddingModelActionConfig] = Field(default_factory=list)
