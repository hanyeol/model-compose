from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import MusicGenerationModelActionConfig
from ..common import CommonMusicGenerationModelComponentConfig
from .common import MusicGenerationModelFamily
from ....common import ModelDriverType

MinimaxMusic3CpuOffload = Literal[ "model", "sequential" ]

class MinimaxMusic3MusicGenerationModelComponentConfig(CommonMusicGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicGenerationModelFamily.MINIMAX_MUSIC3]
    cpu_offload: Optional[MinimaxMusic3CpuOffload] = Field(default=None, description="CPU offload strategy: 'model' uses auto offload (~22 GB), 'sequential' adds group offloading of the language model (fits ~8 GB).")
    actions: List[MusicGenerationModelActionConfig] = Field(default_factory=list, description="Actions this MiniMax-Music3 component exposes to workflows.")
