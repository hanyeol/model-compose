from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonObjectDetectionParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.25, description="Minimum confidence a returned detection must reach.")
    iou_threshold: Union[float, str] = Field(default=0.7, description="IoU threshold used by non-maximum suppression.")
    agnostic_nms: Union[bool, str] = Field(default=False, description="Whether non-maximum suppression is applied across classes rather than per class.")

class CommonObjectDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to detect objects in.")
    labels: Optional[Union[List[str], str]] = Field(default=None, description="Class labels detections are restricted to; unset returns all classes.")
    max_detection_count: Union[int, str] = Field(default=300, description="Maximum number of objects returned per image.")
    crop_margin_ratio: Union[float, str] = Field(default=0.0, description="Margin added around each returned crop image, as a ratio of the box's own width/height")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonObjectDetectionParamsConfig = Field(default_factory=CommonObjectDetectionParamsConfig, description="Detection thresholds and NMS options applied to the detector.")
