from typing import Union, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class ImageGenerationActionMethod(str, Enum):
    GENERATE = "generate"

class CommonImageGenerationParamsConfig(BaseModel):
    pass

class CommonImageGenerationModelActionConfig(CommonModelActionConfig):
    method: ImageGenerationActionMethod = Field(default=ImageGenerationActionMethod.GENERATE, description="Image generation method.")
    prompt: Union[str, List[str]] = Field(..., description="Text prompt describing the image to generate.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to generate simultaneously in each batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific parameters for image generation.")
