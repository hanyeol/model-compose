from typing import Union, Literal, Optional, List, Annotated
from enum import Enum
from pydantic import Field
from ..common import (
    CommonMusicGenerationParamsConfig,
    CommonMusicGenerationModelActionConfig,
    MusicGenerationActionMethod,
)

class Yue2CotMode(str, Enum):
    FULL   = "full"
    MELODY = "melody"
    OFF    = "off"

class Yue2SamplingConfig(CommonMusicGenerationParamsConfig):
    temperature: Optional[Union[float, str]] = Field(default=None, description="Sampling temperature.")
    top_p: Optional[Union[float, str]] = Field(default=None, description="Nucleus sampling probability cutoff.")
    top_k: Optional[Union[int, str]] = Field(default=None, description="Top-k sampling cutoff.")
    repetition_penalty: Optional[Union[float, str]] = Field(default=None, description="Repetition penalty applied within the penalty window.")
    penalty_window: Optional[Union[int, str]] = Field(default=None, description="Token window over which the repetition penalty is computed.")
    min_tokens: Optional[Union[int, str]] = Field(default=None, description="Minimum number of tokens to generate before end tokens are allowed.")
    max_tokens: Optional[Union[int, str]] = Field(default=None, description="Maximum number of tokens to generate.")

class Yue2MusicGenerationParamsConfig(CommonMusicGenerationParamsConfig):
    cot_mode: Union[Yue2CotMode, str] = Field(default=Yue2CotMode.FULL, description="Chain-of-thought mode: full (editable score with chords), melody (melody-only score, best for covers), or off (direct generation).")
    cfg_scale: Optional[Union[float, str]] = Field(default=None, description="Classifier-free guidance scale in [0, 20]; when unset, the checkpoint default is used.")
    abc_sampling: Optional[Yue2SamplingConfig] = Field(default=None, description="Sampling overrides applied when generating the ABC score.")
    semantic_sampling: Optional[Yue2SamplingConfig] = Field(default=None, description="Sampling overrides applied when generating semantic tokens.")

class CommonYue2MusicGenerationModelActionConfig(CommonMusicGenerationModelActionConfig):
    params: Yue2MusicGenerationParamsConfig = Field(default_factory=Yue2MusicGenerationParamsConfig, description="YuE2 music generation parameters.")

class Yue2MusicGenerationModelGenerateActionConfig(CommonYue2MusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.GENERATE]
    style: str = Field(..., description="Text description of the music style, genre, mood, and instrumentation.")
    lyrics: str = Field(..., description="Song lyrics used for vocal generation.")

class Yue2MusicGenerationModelCoverActionConfig(CommonYue2MusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.COVER]
    style: str = Field(..., description="Text description of the target cover style.")
    lyrics: str = Field(..., description="Lyrics to sing over the covered score.")
    abc: str = Field(..., description="ABC score conditioning the cover (typically a melody transcription without chord symbols).")

class Yue2MusicGenerationModelScoreActionConfig(CommonYue2MusicGenerationModelActionConfig):
    method: Literal[MusicGenerationActionMethod.SCORE]
    style: str = Field(..., description="Text description of the music style used to plan the score.")
    lyrics: str = Field(..., description="Song lyrics that shape the planned score.")

Yue2MusicGenerationModelActionConfig = Annotated[
    Union[
        Yue2MusicGenerationModelGenerateActionConfig,
        Yue2MusicGenerationModelCoverActionConfig,
        Yue2MusicGenerationModelScoreActionConfig,
    ],
    Field(discriminator="method")
]
