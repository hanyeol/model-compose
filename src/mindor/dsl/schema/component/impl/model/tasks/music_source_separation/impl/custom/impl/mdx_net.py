from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import MusicSourceSeparationModelActionConfig
from ...common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from .....common import ModelDriver, ModelConfig

class MdxNetMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.MDX_NET]
    model: ModelConfig = Field(..., description="Model repository or local file path. Use 'filename' to select a specific .onnx file within an HF repository.")
    actions: List[MusicSourceSeparationModelActionConfig] = Field(default_factory=list)
