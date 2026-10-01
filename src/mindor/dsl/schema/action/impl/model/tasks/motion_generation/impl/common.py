from typing import Union, Optional
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MotionGenerationActionMethod(str, Enum):
    GENERATE = "generate"

class CommonMotionGenerationParamsConfig(BaseModel):
    pass

class CommonMotionGenerationModelActionConfig(CommonModelActionConfig):
    method: MotionGenerationActionMethod = Field(..., description="Motion generation operation this action performs.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible; ignored by drivers without seed control.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonMotionGenerationParamsConfig = Field(default_factory=CommonMotionGenerationParamsConfig, description="Driver-specific generation parameters.")
