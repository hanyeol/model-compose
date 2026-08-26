from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import YtdlpSubtitleLoaderActionConfig
from .common import CommonSubtitleLoaderComponentConfig, SubtitleLoaderDriver

class YtdlpSubtitleLoaderComponentConfig(CommonSubtitleLoaderComponentConfig):
    driver: Literal[SubtitleLoaderDriver.YTDLP]
    actions: List[YtdlpSubtitleLoaderActionConfig] = Field(default_factory=list)
