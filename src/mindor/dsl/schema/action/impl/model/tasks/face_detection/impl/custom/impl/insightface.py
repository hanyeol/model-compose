from typing import Union, Tuple, List
from pydantic import Field
from ...common import CommonFaceDetectionModelActionConfig, CommonFaceDetectionParamsConfig

class InsightfaceFaceDetectionParamsConfig(CommonFaceDetectionParamsConfig):
    detection_size: Union[Tuple[int, int], List[Union[int, str]], str] = Field(default=(640, 640), description="Detector input resolution as (width, height) in pixels.")
    max_num_faces: Union[int, str] = Field(default=0, description="Maximum number of faces detected per image; 0 means unbounded.")

class InsightfaceFaceDetectionModelActionConfig(CommonFaceDetectionModelActionConfig):
    params: InsightfaceFaceDetectionParamsConfig = Field(default_factory=InsightfaceFaceDetectionParamsConfig, description="Insightface-specific face detection parameters.")
