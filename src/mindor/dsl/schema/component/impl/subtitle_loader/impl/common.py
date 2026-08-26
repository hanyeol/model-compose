from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class SubtitleLoaderDriver(str, Enum):
    LOCAL = "local"
    YTDLP = "ytdlp"

class CommonSubtitleLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SUBTITLE_LOADER]
    driver: SubtitleLoaderDriver = Field(..., description="Backend implementation used for subtitle loading.")
