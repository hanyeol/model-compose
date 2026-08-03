from typing import Union, Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ImageGenerationActionMethod(str, Enum):
    GENERATE = "generate"
    INPAINT  = "inpaint"
    OUTPAINT = "outpaint"

class CommonImageGenerationParamsConfig(BaseModel):
    pass

class CommonImageGenerationModelActionConfig(CommonModelActionConfig):
    method: ImageGenerationActionMethod = Field(default=ImageGenerationActionMethod.GENERATE, description="Image generation method.")
    prompt: Union[str, List[str]] = Field(..., description="Text prompt describing the image to generate.")
    negative_prompt: Optional[Union[str, List[str]]] = Field(default=None, description="Negative prompt(s) describing what to avoid. Ignored by drivers that don't support classifier-free guidance.")
    width: Union[int, str] = Field(default=1024, description="Output image width in pixels.")
    height: Union[int, str] = Field(default=1024, description="Output image height in pixels.")
    num_images_per_prompt: Union[int, str] = Field(default=1, description="Number of images to generate per prompt.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed for deterministic generation.")
    batch_size: Union[int, str] = Field(default=1, description="Images generated simultaneously per batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific image generation parameters.")

class CommonImageGenerationModelInpaintActionConfig(CommonImageGenerationModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image to inpaint.")
    mask_image: Union[str, List[str]] = Field(..., description="Mask image: white pixels mark the area to inpaint, black pixels are preserved.")
