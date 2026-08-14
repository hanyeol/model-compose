from typing import Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class BackgroundRemovalOutputFormat(str, Enum):
    RGBA = "rgba"
    MASK = "mask"

class CommonImageBackgroundRemovalParamsConfig(BaseModel):
    pass

class CommonImageBackgroundRemovalModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to remove backgrounds from.")
    output_format: BackgroundRemovalOutputFormat = Field(default=BackgroundRemovalOutputFormat.RGBA, description="Output format; either an RGBA image with alpha channel or a single-channel mask.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageBackgroundRemovalParamsConfig = Field(..., description="Backend-specific background removal parameters.")
