from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonMusicGenerationParamsConfig(BaseModel):
    duration: Union[int, str] = Field(default=30, description="Duration of the generated music in seconds.")
    bpm: Union[int, str] = Field(default=120, description="Target tempo in beats per minute.")
    key_scale: Optional[str] = Field(default=None, description="Musical key of the generated music (e.g., C, D, Em).")

class CommonMusicGenerationModelActionConfig(CommonModelActionConfig):
    prompt: Union[str, List[str]] = Field(..., description="Text description or descriptions of the music style, genre, mood, and instrumentation.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Song lyrics used when the driver supports vocal generation.")
    seed: Optional[Union[int, str]] = Field(default=None, description="Random seed used to make generation reproducible; ignored by drivers without seed control.")
    batch_size: Union[int, str] = Field(default=1, description="Number of prompts processed per batch.")
    params: CommonMusicGenerationParamsConfig = Field(default_factory=CommonMusicGenerationParamsConfig, description="Duration, tempo, and key parameters applied to generation.")
