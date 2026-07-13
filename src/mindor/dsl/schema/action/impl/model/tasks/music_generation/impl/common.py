from typing import Union, Optional, List
from pydantic import BaseModel, Field
from ...common import CommonModelActionConfig

class CommonMusicGenerationParamsConfig(BaseModel):
    duration: Union[int, str] = Field(default=30, description="Generated music duration in seconds.")
    bpm: Union[int, str] = Field(default=120, description="Beats per minute.")
    key_scale: Optional[str] = Field(default=None, description="Musical key (e.g. 'C', 'D', 'Em').")

class CommonMusicGenerationModelActionConfig(CommonModelActionConfig):
    prompt: Union[str, List[str]] = Field(..., description="Text description of the music style, genre, mood, and instrumentation.")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Song lyrics.")
    batch_size: Union[int, str] = Field(default=1, description="Prompts per batch.")
    params: CommonMusicGenerationParamsConfig = Field(default_factory=CommonMusicGenerationParamsConfig, description="Music generation parameters.")
