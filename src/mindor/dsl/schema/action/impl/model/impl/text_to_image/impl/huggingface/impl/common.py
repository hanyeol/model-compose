from typing import Union, Optional
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonTextToImageModelActionConfig

class HuggingfaceTextToImageModelArchitecture(str, Enum):
    SDXL          = "sdxl"
    FLUX          = "flux"
    HUNYUAN_IMAGE = "hunyuan-image"

class CommonHuggingfaceTextToImageParamsConfig(BaseModel):
    num_inference_steps: Union[int, str] = Field(default=30, description="Number of denoising steps.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")

class CommonHuggingfaceTextToImageModelActionConfig(CommonTextToImageModelActionConfig):
    params: CommonHuggingfaceTextToImageParamsConfig = Field(default_factory=CommonHuggingfaceTextToImageParamsConfig, description="Image generation configuration parameters.")
