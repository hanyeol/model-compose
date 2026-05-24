from typing import Union, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonImageGenerationParamsConfig(BaseModel):
    pass

class CommonImageGenerationModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Text prompt describing the image to generate.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to generate simultaneously in each batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific parameters for image generation.")
