from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MediaDownloaderActionConfig
from .common import CommonMediaDownloaderComponentConfig, MediaDownloaderDriver

class YtdlpMediaDownloaderComponentConfig(CommonMediaDownloaderComponentConfig):
    driver: Literal[MediaDownloaderDriver.YTDLP]
    actions: List[MediaDownloaderActionConfig] = Field(default_factory=list)
