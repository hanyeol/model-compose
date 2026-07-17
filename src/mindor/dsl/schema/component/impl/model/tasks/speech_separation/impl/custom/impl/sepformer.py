from typing import Literal, List, Optional, Union
from pydantic import Field
from mindor.dsl.schema.action import SpeechSeparationModelActionConfig
from ...common import CommonSpeechSeparationModelComponentConfig
from .common import SpeechSeparationModelFamily
from .....common import ModelDriver, ModelConfig

class SepformerSpeechSeparationModelComponentConfig(CommonSpeechSeparationModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[SpeechSeparationModelFamily.SEPFORMER]
    model: Optional[Union[str, ModelConfig]] = Field(default=None, description="SpeechBrain SepFormer checkpoint (e.g. 'speechbrain/sepformer-wsj02mix'). If omitted, defaults are chosen from num_speakers.")
    actions: List[SpeechSeparationModelActionConfig] = Field(default_factory=list)
