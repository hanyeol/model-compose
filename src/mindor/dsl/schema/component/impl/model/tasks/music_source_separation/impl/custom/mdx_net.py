from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import MdxNetMusicSourceSeparationModelActionConfig
from ..common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from ....common import ModelDriverType, ModelConfig

class MdxNetMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.MDX_NET]
    model: ModelConfig = Field(..., description="Model identifier — a HuggingFace repo ID or a local path; set `filename` to pick a specific .onnx file within the repo.")
    actions: List[MdxNetMusicSourceSeparationModelActionConfig] = Field(default_factory=list, description="Actions this music source separation component exposes to workflows.")
