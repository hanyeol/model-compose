from typing import Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class BackgroundRemovalOutputFormat(str, Enum):
    CUTOUT = "cutout"
    MASK   = "mask"

class CommonImageBackgroundRemovalParamsConfig(BaseModel):
    pass

class CommonImageBackgroundRemovalModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image or list of images to remove backgrounds from.")
    format: Union[BackgroundRemovalOutputFormat, str] = Field(default=BackgroundRemovalOutputFormat.CUTOUT, description="Output format; either the subject on a transparent background or a single-channel mask.")
    batch_size: Union[int, str] = Field(default=1, description="Number of input images processed per batch.")
    params: CommonImageBackgroundRemovalParamsConfig = Field(..., description="Backend-specific background removal parameters.")
