from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FacenetFaceEmbeddingModelActionConfig
from ..common import CommonFaceEmbeddingModelComponentConfig
from .common import FaceEmbeddingModelFamily
from ....common import ModelDriverType

class FacenetFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[FaceEmbeddingModelFamily.FACENET]
    actions: List[FacenetFaceEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this face embedding component exposes to workflows.")
