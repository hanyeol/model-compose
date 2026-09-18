from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MediaDownloaderDriverType(str, Enum):
    YTDLP = "ytdlp"

class CommonMediaDownloaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MEDIA_DOWNLOADER]
    driver: MediaDownloaderDriverType = Field(..., description="Backend implementation used for media downloading.")
