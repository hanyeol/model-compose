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
    batch_size: Union[int, str] = Field(default=1, description="Number of images to generate simultaneously in each batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific parameters for image generation.")

class CommonImageGenerationModelInpaintActionConfig(CommonImageGenerationModelActionConfig):
    image: Union[str, List[str]] = Field(..., description="Input image to be inpainted.")
    mask_image: Union[str, List[str]] = Field(..., description="Mask image where white pixels mark the area to be inpainted and black pixels are preserved.")
