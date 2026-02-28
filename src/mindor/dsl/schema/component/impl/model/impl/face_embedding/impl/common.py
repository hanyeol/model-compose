from typing import Literal, Optional, Tuple
from enum import Enum
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType, ModelDriver

class FaceEmbeddingModelFamily(str, Enum):
    INSIGHTFACE = "insightface"
    FACENET     = "facenet"
    DLIB        = "dlib"

class CommonFaceEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_EMBEDDING]
    driver: ModelDriver = Field(default=ModelDriver.CUSTOM)
    family: FaceEmbeddingModelFamily = Field(..., description="Face embedding model family.")
    version: Optional[str] = Field(default=None, description="Model version or variant.")
    input_size: Tuple[int, int] = Field(default=(112, 112), description="Input image size (width, height).")
