from typing import Union, Tuple, List
from pydantic import Field
from ..common import CommonFaceTrackingModelActionConfig, CommonFaceTrackingParamsConfig

class InsightfaceFaceTrackingParamsConfig(CommonFaceTrackingParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.5, description="Minimum detection confidence a face must reach.")
    detection_size: Union[Tuple[int, int], List[Union[int, str]], str] = Field(default=(640, 640), description="Detector input resolution as (width, height) in pixels.")

class InsightfaceFaceTrackingModelActionConfig(CommonFaceTrackingModelActionConfig):
    return_gender_age: Union[bool, str] = Field(default=False, description="Whether gender and age are included on each face; also emitted per-frame when 'return_detections' is enabled.")
    params: InsightfaceFaceTrackingParamsConfig = Field(default_factory=InsightfaceFaceTrackingParamsConfig, description="Insightface-specific face tracking parameters.")
