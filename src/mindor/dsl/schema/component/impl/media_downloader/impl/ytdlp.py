from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MediaDownloaderActionConfig
from .common import CommonMediaDownloaderComponentConfig, MediaDownloaderDriverType

class YtdlpMediaDownloaderComponentConfig(CommonMediaDownloaderComponentConfig):
    driver: Literal[MediaDownloaderDriverType.YTDLP]
    actions: List[MediaDownloaderActionConfig] = Field(default_factory=list)
