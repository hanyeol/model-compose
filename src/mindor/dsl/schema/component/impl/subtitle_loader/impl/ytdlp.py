from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import YtdlpSubtitleLoaderActionConfig
from .common import CommonSubtitleLoaderComponentConfig, SubtitleLoaderDriverType

class YtdlpSubtitleLoaderComponentConfig(CommonSubtitleLoaderComponentConfig):
    driver: Literal[SubtitleLoaderDriverType.YTDLP]
    actions: List[YtdlpSubtitleLoaderActionConfig] = Field(default_factory=list)
