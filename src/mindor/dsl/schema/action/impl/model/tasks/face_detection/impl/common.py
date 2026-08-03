from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceDetectionParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence threshold (0.0 - 1.0).")

class CommonFaceDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s) for face detection.")
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether to return facial landmarks when supported by the driver.")
    batch_size: Union[int, str] = Field(default=1, description="Images per batch.")
    params: CommonFaceDetectionParamsConfig = Field(default_factory=CommonFaceDetectionParamsConfig, description="Face detection parameters.")
