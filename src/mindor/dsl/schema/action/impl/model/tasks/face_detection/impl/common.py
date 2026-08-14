from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonFaceDetectionParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence a face must reach, from 0.0 to 1.0.")

class CommonFaceDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to detect faces in.")
    bounding_box_padding: Union[float, str] = Field(default=0.0, description="Ratio by which each detected bounding box is expanded outward.")
    return_landmarks: Union[bool, str] = Field(default=False, description="Whether facial landmarks are included in the result when the driver supports them.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonFaceDetectionParamsConfig = Field(default_factory=CommonFaceDetectionParamsConfig, description="Detection thresholds and options applied to the face detector.")
