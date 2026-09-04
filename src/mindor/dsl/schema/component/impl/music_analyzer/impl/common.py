from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MusicAnalyzerDriver(str, Enum):
    NATIVE = "native"

class CommonMusicAnalyzerComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MUSIC_ANALYZER]
    driver: MusicAnalyzerDriver = Field(..., description="Backend implementation used for music analysis.")
