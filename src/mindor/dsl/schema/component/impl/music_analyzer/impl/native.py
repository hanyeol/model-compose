from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from .common import CommonMusicAnalyzerComponentConfig, MusicAnalyzerDriverType

class NativeMusicAnalyzerComponentConfig(CommonMusicAnalyzerComponentConfig):
    driver: Literal[MusicAnalyzerDriverType.NATIVE]
    actions: List[MusicAnalyzerActionConfig] = Field(default_factory=list)
