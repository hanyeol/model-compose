from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicScoreRendererDriverType(str, Enum):
    VEROVIO = "verovio"

class CommonMusicScoreRendererComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_SCORE_RENDERER]
    driver: MusicScoreRendererDriverType = Field(..., description="Backend implementation used for score rendering.")
