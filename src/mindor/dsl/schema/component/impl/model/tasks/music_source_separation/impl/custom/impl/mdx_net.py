from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import MusicSourceSeparationModelActionConfig
from ...common import CommonMusicSourceSeparationModelComponentConfig
from .common import MusicSourceSeparationModelFamily
from .....common import ModelDriver, ModelConfig

class MdxNetMusicSourceSeparationModelComponentConfig(CommonMusicSourceSeparationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[MusicSourceSeparationModelFamily.MDX_NET]
    model: Union[str, ModelConfig] = Field(..., description="MDX-Net ONNX model source. Point to a HuggingFace repository (e.g. 'seanghay/uvr_models') and use 'filename' to select the specific .onnx file (e.g. 'UVR-MDX-NET-Voc_FT.onnx').")
    actions: List[MusicSourceSeparationModelActionConfig] = Field(default_factory=list)
