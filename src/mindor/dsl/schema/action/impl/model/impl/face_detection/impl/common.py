from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonFaceDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s) for face detection.")
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum detection confidence threshold (0.0 - 1.0).")
    include_landmarks: Union[bool, str] = Field(default=False, description="Include facial landmarks in the result when supported by the driver.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
