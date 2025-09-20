from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonFaceEmbeddingModelActionConfig

class DlibFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    # Dlib specific settings
    predictor_model: str = Field(default="shape_predictor_68_face_landmarks.dat", description="Path to dlib facial landmark predictor model.")
    face_rec_model: str = Field(default="dlib_face_recognition_resnet_model_v1.dat", description="Path to dlib face recognition model.")

    # Detection settings
    upsampling: int = Field(default=1, description="Number of times to upsample the image for face detection.")
    detection_threshold: float = Field(default=0.0, description="Detection confidence threshold.")

    # Landmark settings
    num_jitters: int = Field(default=1, description="Number of times to re-sample face for encoding (higher = more accurate but slower).")
    landmark_model: str = Field(default="68_point", description="Facial landmark model type (5_point, 68_point).")
