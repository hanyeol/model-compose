from typing import Union, Annotated
from pydantic import Field
from .common import (
    CommonMusicPitchCorrectorCorrectActionConfig,
    CommonMusicPitchCorrectorPlanActionConfig,
    CommonMusicPitchCorrectorApplyActionConfig,
)

class WorldMusicPitchCorrectorCorrectActionConfig(CommonMusicPitchCorrectorCorrectActionConfig):
    formant_shift: Union[float, str] = Field(default=0.0, description="Formant shift in semitones; 0 keeps the original timbre.")

class WorldMusicPitchCorrectorPlanActionConfig(CommonMusicPitchCorrectorPlanActionConfig):
    pass

class WorldMusicPitchCorrectorApplyActionConfig(CommonMusicPitchCorrectorApplyActionConfig):
    formant_shift: Union[float, str] = Field(default=0.0, description="Formant shift in semitones; 0 keeps the original timbre.")

WorldMusicPitchCorrectorActionConfig = Annotated[
    Union[
        WorldMusicPitchCorrectorCorrectActionConfig,
        WorldMusicPitchCorrectorPlanActionConfig,
        WorldMusicPitchCorrectorApplyActionConfig,
    ],
    Field(discriminator="method")
]
