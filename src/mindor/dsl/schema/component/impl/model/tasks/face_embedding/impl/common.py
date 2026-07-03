from typing import Literal, Optional, Tuple
from pydantic import Field
from ...common import CommonModelComponentConfig, ModelTaskType

class CommonFaceEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.FACE_EMBEDDING]
    version: Optional[str] = Field(default=None, description="Model version or variant.")
    input_size: Tuple[int, int] = Field(default=(112, 112), description="Input image size (width, height).")
