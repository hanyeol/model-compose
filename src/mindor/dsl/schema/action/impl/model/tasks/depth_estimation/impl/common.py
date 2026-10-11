from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonDepthEstimationParamsConfig(BaseModel):
    pass

class CommonDepthEstimationModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to estimate depth for.")
    invert: Union[bool, str] = Field(default=False, description="Whether to invert the depth map so that farther pixels are brighter.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonDepthEstimationParamsConfig = Field(..., description="Backend-specific depth estimation parameters.")
