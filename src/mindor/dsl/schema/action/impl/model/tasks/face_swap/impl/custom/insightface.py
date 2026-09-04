from typing import Union, Tuple, List
from pydantic import Field
from ..common import CommonFaceSwapModelActionConfig, CommonFaceSwapParamsConfig

class InsightfaceFaceSwapParamsConfig(CommonFaceSwapParamsConfig):
    detection_threshold: Union[float, str] = Field(default=0.5, description="Minimum detection confidence a face must reach.")
    detection_size: Union[Tuple[int, int], List[Union[int, str]], str] = Field(default=(640, 640), description="Detector input resolution as (width, height) in pixels.")

class InsightfaceFaceSwapModelActionConfig(CommonFaceSwapModelActionConfig):
    params: InsightfaceFaceSwapParamsConfig = Field(default_factory=InsightfaceFaceSwapParamsConfig, description="Insightface-specific face swap parameters.")
