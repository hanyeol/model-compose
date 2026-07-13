from typing import Union, List
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
    batch_size: Union[int, str] = Field(default=1, description="Images generated simultaneously per batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific image generation parameters.")

class CommonImageGenerationModelInpaintActionConfig(CommonImageGenerationModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image to inpaint.")
    mask_image: Union[str, List[str]] = Field(..., description="Mask image: white pixels mark the area to inpaint, black pixels are preserved.")
