from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import NativeMusicSynthesizerActionConfig
from .common import CommonMusicSynthesizerComponentConfig, MusicSynthesizerDriverType

class NativeMusicSynthesizerComponentConfig(CommonMusicSynthesizerComponentConfig):
    driver: Literal[MusicSynthesizerDriverType.NATIVE]
    actions: List[NativeMusicSynthesizerActionConfig] = Field(default_factory=list)
