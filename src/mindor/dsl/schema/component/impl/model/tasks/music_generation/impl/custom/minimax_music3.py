from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriverType

class MinimaxMusic3MusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicGenerationModelFamily.MINIMAX_MUSIC3]
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this MiniMax-Music3 component exposes to workflows.")
