from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicPerformanceModelActionConfig
from ..common import CommonMusicPerformanceModelComponentConfig
from .common import MusicPerformanceModelFamily
from ....common import ModelDriverType

class VirtuosoNetMusicPerformanceModelComponentConfig(CommonMusicPerformanceModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicPerformanceModelFamily.VIRTUOSO_NET]
    actions: List[MusicPerformanceModelActionConfig] = Field(default_factory=list, description="Actions this VirtuosoNet component exposes to workflows.")
