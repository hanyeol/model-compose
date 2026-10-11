from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicScoreLoaderDriverType(str, Enum):
    LOCAL = "local"

class CommonMusicScoreLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_SCORE_LOADER]
    driver: MusicScoreLoaderDriverType = Field(..., description="Backend implementation used for score loading.")
