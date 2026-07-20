from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonObjectDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s).")
    labels: Optional[Union[List[str], str]] = Field(default=None, description="Restrict detections to specific labels. If omitted, returns all.")
    min_confidence: Union[float, str] = Field(default=0.25, description="Minimum detection confidence.")
    max_object_count: Union[int, str] = Field(default=300, description="Maximum objects per image.")
    iou_threshold: Union[float, str] = Field(default=0.7, description="IoU threshold for non-maximum suppression.")
    agnostic_nms: Union[bool, str] = Field(default=False, description="Perform class-agnostic non-maximum suppression.")
    batch_size: Union[int, str] = Field(default=1, description="Batch size.")
