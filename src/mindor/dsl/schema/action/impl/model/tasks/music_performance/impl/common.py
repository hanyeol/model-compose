from typing import Union, Optional
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MusicPerformanceActionMethod(str, Enum):
    RENDER = "render"

class CommonMusicPerformanceParamsConfig(BaseModel):
    pass

class CommonMusicPerformanceModelActionConfig(CommonModelActionConfig):
    method: MusicPerformanceActionMethod = Field(..., description="Music performance operation this action performs.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible; ignored by drivers without seed control.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonMusicPerformanceParamsConfig = Field(default_factory=CommonMusicPerformanceParamsConfig, description="Driver-specific performance parameters.")
