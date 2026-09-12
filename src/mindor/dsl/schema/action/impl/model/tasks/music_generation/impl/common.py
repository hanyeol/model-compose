from typing import Union, Optional, List
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class MusicGenerationActionMethod(str, Enum):
    GENERATE  = "generate"
    COVER     = "cover"
    REWRITE   = "rewrite"
    EXTEND    = "extend"
    LAYER     = "layer"
    ACCOMPANY = "accompany"

class CommonMusicGenerationParamsConfig(BaseModel):
    pass

class CommonMusicGenerationModelActionConfig(CommonModelActionConfig):
    method: MusicGenerationActionMethod = Field(..., description="Music generation operation this action performs.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible; ignored by drivers without seed control.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonMusicGenerationParamsConfig = Field(default_factory=CommonMusicGenerationParamsConfig, description="Driver-specific generation parameters.")
