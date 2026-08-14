from typing import Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ColorFormat(str, Enum):
    RGB = "rgb"
    BGR = "bgr"

class CommonImageUpscaleParamsConfig(BaseModel):
    pass

class CommonImageUpscaleModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to upscale.")
    color_format: ColorFormat = Field(default=ColorFormat.RGB, description="Color channel order used by the model.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageUpscaleParamsConfig = Field(..., description="Backend-specific image upscale parameters.")
