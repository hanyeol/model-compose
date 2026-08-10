from typing import Union, Tuple
from pydantic import Field
from ...common import CommonFaceSwapModelActionConfig, CommonFaceSwapParamsConfig

class InsightfaceFaceSwapParamsConfig(CommonFaceSwapParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.5, description="Detection threshold for face detection.")
    detection_size: Tuple[int, int] = Field(default=(640, 640), description="Detection input size.")

class InsightfaceFaceSwapModelActionConfig(CommonFaceSwapModelActionConfig):
    params: InsightfaceFaceSwapParamsConfig = Field(default_factory=InsightfaceFaceSwapParamsConfig, description="Face swap parameters.")
