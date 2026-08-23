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
    duration: Union[int, str] = Field(default=30, description="Duration of the generated music in seconds.")
    bpm: Union[int, str] = Field(default=120, description="Target tempo in beats per minute.")
    key_scale: Optional[str] = Field(default=None, description="Musical key of the generated music (e.g., C, D, Em).")

class CommonMusicGenerationModelActionConfig(CommonModelActionConfig):
    method: MusicGenerationActionMethod = Field(..., description="Music generation operation this action performs.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible; ignored by drivers without seed control.")
    batch_size: Union[int, str] = Field(default=1, description="Number of inputs processed per batch.")
    params: CommonMusicGenerationParamsConfig = Field(default_factory=CommonMusicGenerationParamsConfig, description="Duration, tempo, and key parameters applied to generation.")
