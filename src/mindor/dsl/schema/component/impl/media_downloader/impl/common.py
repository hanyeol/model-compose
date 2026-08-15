from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class MediaDownloaderDriver(str, Enum):
    YTDLP = "ytdlp"

class CommonMediaDownloaderComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.MEDIA_DOWNLOADER]
    driver: MediaDownloaderDriver = Field(..., description="Backend implementation used for media downloading.")
