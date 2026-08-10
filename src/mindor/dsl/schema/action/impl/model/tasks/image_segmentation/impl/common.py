from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ImageSegmentationBoxPrompt(BaseModel):
    x: Union[int, str] = Field(..., description="X coordinate of the top-left corner.")
    y: Union[int, str] = Field(..., description="Y coordinate of the top-left corner.")
    width: Union[int, str] = Field(..., description="Box width in pixels.")
    height: Union[int, str] = Field(..., description="Box height in pixels.")

class CommonImageSegmentationParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum segment confidence.")
    min_area: Optional[Union[int, str]] = Field(default=None, description="Minimum mask area in pixels. If omitted, no filter is applied.")

class CommonImageSegmentationModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image(s).")
    box_prompt: Optional[Union[ImageSegmentationBoxPrompt, List[ImageSegmentationBoxPrompt], str]] = Field(default=None, description="Box prompt(s) as `{x, y, width, height}` (single) or a list of them.")
    max_segment_count: Union[int, str] = Field(default=100, description="Maximum segments per image.")
    return_mask: Union[bool, str] = Field(default=True, description="Return per-segment binary mask as PNG.")
    batch_size: Union[int, str] = Field(default=1, description="Batch size.")
    params: CommonImageSegmentationParamsConfig = Field(default_factory=CommonImageSegmentationParamsConfig, description="Image segmentation parameters.")
