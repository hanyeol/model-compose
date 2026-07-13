from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceEmbeddingModelActionConfig

class InsightfaceFaceEmbeddingModelActionConfig(CommonFaceEmbeddingModelActionConfig):
    # Detection settings
    detection_threshold: Union[float, str] = Field(default=0.6, description="Detection threshold for face detection.")
    recognition_threshold: Union[float, str] = Field(default=0.5, description="Recognition threshold for face verification.")
    nms_threshold: Union[float, str] = Field(default=0.4, description="Non-maximum suppression threshold.")
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")
    max_num_faces: Union[int, str] = Field(default=1, description="Maximum number of faces to detect per image.")

    # Output options
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether to return facial landmarks.")
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether to return gender/age predictions.")
