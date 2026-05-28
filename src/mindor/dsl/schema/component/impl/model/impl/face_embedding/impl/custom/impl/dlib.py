from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import DlibFaceEmbeddingModelActionConfig
from ...common import CommonFaceEmbeddingModelComponentConfig
from .common import FaceEmbeddingModelFamily
from .....common import ModelDriver

class DlibFaceEmbeddingModelComponentConfig(CommonFaceEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[FaceEmbeddingModelFamily.DLIB]
    actions: List[DlibFaceEmbeddingModelActionConfig] = Field(default_factory=list)
