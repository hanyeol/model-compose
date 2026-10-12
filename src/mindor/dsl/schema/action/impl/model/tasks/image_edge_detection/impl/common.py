from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonImageEdgeDetectionParamsConfig(BaseModel):
    pass

class CommonImageEdgeDetectionModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to detect edges in.")
    invert: Union[bool, str] = Field(default=False, description="Whether to invert the edge map so that edges are dark on a bright background.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageEdgeDetectionParamsConfig = Field(..., description="Family-specific edge detection parameters.")
