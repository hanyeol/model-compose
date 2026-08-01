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
    image: Union[str, List[str]] = Field(..., description="Input image to remove background from.")
    output_format: BackgroundRemovalOutputFormat = Field(default=BackgroundRemovalOutputFormat.RGBA, description="Output format: RGBA image with alpha channel, or single-channel mask.")
    batch_size: Union[int, str] = Field(default=1, description="Images per batch.")
    params: CommonImageBackgroundRemovalParamsConfig = Field(..., description="Image background removal parameters.")
