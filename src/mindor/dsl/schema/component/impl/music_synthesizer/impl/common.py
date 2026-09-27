from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicSynthesizerDriverType(str, Enum):
    NATIVE = "native"

class CommonMusicSynthesizerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_SYNTHESIZER]
    driver: MusicSynthesizerDriverType = Field(..., description="Backend implementation used for music synthesis.")
