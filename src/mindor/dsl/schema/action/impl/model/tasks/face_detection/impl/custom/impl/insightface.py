from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceDetectionModelActionConfig, CommonFaceDetectionParamsConfig

class InsightfaceFaceDetectionParamsConfig(CommonFaceDetectionParamsConfig):
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")
    max_num_faces: Union[int, str] = Field(default=0, description="Maximum number of faces to detect per image. 0 disables the limit.")

class InsightfaceFaceDetectionModelActionConfig(CommonFaceDetectionModelActionConfig):
    params: InsightfaceFaceDetectionParamsConfig = Field(default_factory=InsightfaceFaceDetectionParamsConfig, description="Face detection parameters.")
