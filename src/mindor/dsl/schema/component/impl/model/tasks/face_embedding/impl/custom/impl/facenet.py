from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import FacenetFaceEmbeddingModelActionConfig
from ...common import CommonFaceEmbeddingModelComponentConfig
from .common import FaceEmbeddingModelFamily
from .....common import ModelDriver

class FacenetFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceEmbeddingModelFamily.FACENET]
    actions: List[FacenetFaceEmbeddingModelActionConfig] = Field(default_factory=list)
