from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceEmbeddingModelActionConfig, CommonFaceEmbeddingParamsConfig

class InsightfaceFaceEmbeddingParamsConfig(CommonFaceEmbeddingParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.6, description="Detection threshold for face detection.")
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")
    max_num_faces: Union[int, str] = Field(default=1, description="Maximum number of faces to detect per image.")

class InsightfaceFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether to return facial landmarks.")
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether to return gender/age predictions.")
    params: InsightfaceFaceEmbeddingParamsConfig = Field(default_factory=InsightfaceFaceEmbeddingParamsConfig, description="Face embedding parameters.")
