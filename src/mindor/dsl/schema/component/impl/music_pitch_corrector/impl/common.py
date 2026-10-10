from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicPitchCorrectorDriverType(str, Enum):
    WORLD = "world"

class CommonMusicPitchCorrectorComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_PITCH_CORRECTOR]
    driver: MusicPitchCorrectorDriverType = Field(..., description="Resynthesis engine used to apply pitch corrections.")
