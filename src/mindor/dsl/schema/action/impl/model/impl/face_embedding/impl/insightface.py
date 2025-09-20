from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonFaceEmbeddingModelActionConfig

class InsightfaceFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    # InsightFace specific settings
    det_thresh: Union[float, str] = Field(default=0.6, description="Detection threshold for face detection.")
    rec_thresh: Union[float, str] = Field(default=0.5, description="Recognition threshold for face verification.")
    nms_thresh: Union[float, str] = Field(default=0.4, description="Non-maximum suppression threshold.")

    # Advanced settings
    det_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")
    max_num_faces: Union[int, str] = Field(default=1, description="Maximum number of faces to detect per image.")

    # Output options
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether to return facial landmarks.")
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether to return gender and age predictions.")
