from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeMusicAnalyzerActionConfig
from .common import CommonMusicAnalyzerComponentConfig, MusicAnalyzerDriverType

class NativeMusicAnalyzerComponentConfig(CommonMusicAnalyzerComponentConfig):
    driver: Literal[MusicAnalyzerDriverType.NATIVE]
    actions: List[NativeMusicAnalyzerActionConfig] = Field(default_factory=list)
