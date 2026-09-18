from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class SubtitleLoaderDriverType(str, Enum):
    LOCAL = "local"
    YTDLP = "ytdlp"

class CommonSubtitleLoaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.SUBTITLE_LOADER]
    driver: SubtitleLoaderDriverType = Field(..., description="Backend implementation used for subtitle loading.")
