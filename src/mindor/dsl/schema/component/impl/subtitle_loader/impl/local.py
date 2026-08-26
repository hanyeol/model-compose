from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LocalSubtitleLoaderActionConfig
from .common import CommonSubtitleLoaderComponentConfig, SubtitleLoaderDriver

class LocalSubtitleLoaderComponentConfig(CommonSubtitleLoaderComponentConfig):
    driver: Literal[SubtitleLoaderDriver.LOCAL]
    actions: List[LocalSubtitleLoaderActionConfig] = Field(default_factory=list)
