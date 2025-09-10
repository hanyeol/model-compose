from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from ...common import CommonModelActionConfig

class CommonImageGenerationParamsConfig(BaseModel):
    pass

class CommonImageGenerationModelActionConfig(CommonModelActionConfig):
    text: Union[str, List[str]] = Field(..., description="Text prompt describing the image to generate.")
    batch_size: Union[int, str] = Field(default=1, description="Number of images to generate simultaneously in each batch.")
    params: CommonImageGenerationParamsConfig = Field(..., description="Model-specific parameters for image generation.")
