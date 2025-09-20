from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonFaceEmbeddingModelActionConfig

class FacenetFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    # FaceNet specific settings
    margin: float = Field(default=44.0, description="Margin for face cropping.")
    image_size: int = Field(default=160, description="Input image size for FaceNet (square).")
    prewhiten: bool = Field(default=True, description="Whether to prewhiten input images.")

    # Detection settings
    min_face_size: int = Field(default=20, description="Minimum face size for detection.")
    detection_threshold: Tuple[float, float, float] = Field(
        default=(0.6, 0.7, 0.7),
        description="MTCNN detection thresholds for P-Net, R-Net, and O-Net."
    )
    factor: float = Field(default=0.709, description="Scale factor for MTCNN.")
