from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import LocalSubtitleLoaderActionConfig
from .common import CommonSubtitleLoaderComponentConfig, SubtitleLoaderDriverType

class LocalSubtitleLoaderComponentConfig(CommonSubtitleLoaderComponentConfig):
    driver: Literal[SubtitleLoaderDriverType.LOCAL]
    actions: List[LocalSubtitleLoaderActionConfig] = Field(default_factory=list)
