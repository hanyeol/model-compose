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
    image: Union[str, List[str]] = Field(..., description="Input image to upscale.")
    batch_size: Union[int, str] = Field(default=1, description="Images per batch.")
    color_format: ColorFormat = Field(default=ColorFormat.RGB, description="Color format for image processing.")
    params: CommonImageUpscaleParamsConfig = Field(..., description="Image upscale parameters.")
