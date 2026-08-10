from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceTrackingModelActionConfig, CommonFaceTrackingParamsConfig

class InsightfaceFaceTrackingParamsConfig(CommonFaceTrackingParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.5, description="Detection threshold for face detection.")
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")

class InsightfaceFaceTrackingModelActionConfig(CommonFaceTrackingModelActionConfig):
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether to include the track's gender/age from its highest-scoring frame.")
    params: InsightfaceFaceTrackingParamsConfig = Field(default_factory=InsightfaceFaceTrackingParamsConfig, description="Face tracking parameters.")
