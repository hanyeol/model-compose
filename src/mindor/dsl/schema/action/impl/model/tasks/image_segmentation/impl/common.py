from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ImageSegmentationBoxPrompt(BaseModel):
    x: Union[int, str] = Field(..., description="X coordinate of the prompt box's top-left corner, in pixels.")
    y: Union[int, str] = Field(..., description="Y coordinate of the prompt box's top-left corner, in pixels.")
    width: Union[int, str] = Field(..., description="Prompt box width in pixels.")
    height: Union[int, str] = Field(..., description="Prompt box height in pixels.")

class CommonImageSegmentationParamsConfig(BaseModel):
    min_confidence: Union[float, str] = Field(default=0.5, description="Minimum confidence a returned segment must reach.")
    min_area: Optional[Union[int, str]] = Field(default=None, description="Minimum mask area in pixels; unset applies no filter.")

class CommonImageSegmentationModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to segment.")
    box_prompt: Optional[Union[ImageSegmentationBoxPrompt, List[ImageSegmentationBoxPrompt], str]] = Field(default=None, description="Box prompt or prompts steering segmentation, each as `{x, y, width, height}`.")
    max_segment_count: Union[int, str] = Field(default=100, description="Maximum number of segments returned per image.")
    return_mask: Union[bool, str] = Field(default=True, description="Whether the per-segment binary mask is returned as a PNG.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageSegmentationParamsConfig = Field(default_factory=CommonImageSegmentationParamsConfig, description="Confidence and area filters applied to segmentation output.")
