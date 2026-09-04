from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicAnalyzerActionConfig
from .common import CommonMusicAnalyzerComponentConfig, MusicAnalyzerDriver

class NativeMusicAnalyzerComponentConfig(CommonMusicAnalyzerComponentConfig):
    driver: Literal[MusicAnalyzerDriver.NATIVE]
    actions: List[MusicAnalyzerActionConfig] = Field(default_factory=list)
