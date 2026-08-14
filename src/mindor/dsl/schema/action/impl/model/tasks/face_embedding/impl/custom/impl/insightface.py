from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceEmbeddingModelActionConfig, CommonFaceEmbeddingParamsConfig

class InsightfaceFaceEmbeddingParamsConfig(CommonFaceEmbeddingParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.6, description="Minimum detection confidence a face must reach.")
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detector input resolution as (width, height) in pixels.")
    max_num_faces: Union[int, str] = Field(default=1, description="Maximum number of faces detected per image.")

class InsightfaceFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether facial landmarks are included in the result.")
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether gender and age predictions are included in the result.")
    params: InsightfaceFaceEmbeddingParamsConfig = Field(default_factory=InsightfaceFaceEmbeddingParamsConfig, description="Insightface-specific face embedding parameters.")
