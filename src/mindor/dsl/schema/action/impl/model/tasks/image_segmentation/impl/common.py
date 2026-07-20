from typing import Union, Optional, List
from pydantic import Field
from ...common import CommonModelActionConfig

class CommonImageSegmentationModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s).")
    box_prompt: Optional[Union[List[List[Union[int, float]]], List[Union[int, float]], str]] = Field(default=None, description="Box prompt(s) as [x, y, width, height].")
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum segment confidence.")
    min_area: Optional[Union[int, str]] = Field(default=None, description="Minimum mask area in pixels. If omitted, no filter is applied.")
    max_segment_count: Union[int, str] = Field(default=100, description="Maximum segments per image.")
    return_mask: Union[bool, str] = Field(default=True, description="Return per-segment binary mask as PNG.")
    batch_size: Union[int, str] = Field(default=1, description="Batch size.")
