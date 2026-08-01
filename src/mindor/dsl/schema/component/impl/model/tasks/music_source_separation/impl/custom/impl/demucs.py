from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import MusicSourceSeparationModelActionConfig
from ...common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from .....common import ModelDriver, ModelConfig

class DemucsMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.DEMUCS]
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="Demucs pretrained model name (e.g. 'htdemucs_ft', 'htdemucs', 'mdx_extra'). Defaults to 'htdemucs_ft'.")
    actions: List[MusicSourceSeparationModelActionConfig] = Field(default_factory=list)
