from typing import Union, Literal, Optional, List, Annotated
from pydantic import Field
from ..common import (
    CommonMusicGenerationParamsConfig,
    CommonMusicGenerationModelActionConfig,
    MusicGenerationActionMethod,
)

class MinimaxMusic3MusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    duration: Union[float, str] = Field(default=60.0, description="Duration of the generated music in seconds (up to 300).")

class CommonMinimaxMusic3MusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: MinimaxMusic3MusicGenerationParamsConfig = Field(default_factory=MinimaxMusic3MusicGenerationParamsConfig, description="MiniMax-Music3 music generation parameters.")

class MinimaxMusic3MusicGenerationModelGenerateActionConfig(CommonMinimaxMusic3MusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.GENERATE]
    prompt: Union[str, List[str]] = Field(..., description="Structured music description (genre, BPM, key, mood, vocals, arrangement).")
    lyrics: Optional[Union[str, List[Optional[str]]]] = Field(default=None, description="Song lyrics with section tags such as [verse], [chorus], [bridge] on their own lines.")

MinimaxMusic3MusicGenerationModelActionConfig = Annotated[
    Union[
        MinimaxMusic3MusicGenerationModelGenerateActionConfig,
    ],
    Field(discriminator="method")
]
