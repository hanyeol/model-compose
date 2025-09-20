from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class ColorFormat(str, Enum):
    RGB = "rgb"
    BGR = "bgr"

class CommonImageUpscaleParamsConfig(BaseModel):
    color_format: ColorFormat = Field(default=ColorFormat.RGB, description="Color format for image processing.")

class CommonImageUpscaleModelActionConfig(CommonModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image to upscale.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to process in a single batch.")
    params: CommonImageUpscaleParamsConfig = Field(..., description="Image upscale configuration parameters.")
