from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import AudioTextAlignmentModelActionConfig
from .common import CommonAudioTextAlignmentModelComponentConfig
from ...common import ModelDriver

class HuggingfaceAudioTextAlignmentModelArchitecture(str, Enum):
    AUTO     = "auto"
    WAV2VEC2 = "wav2vec2"

class HuggingfaceAudioTextAlignmentModelComponentConfig(CommonAudioTextAlignmentModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    architecture: HuggingfaceAudioTextAlignmentModelArchitecture = Field(default=HuggingfaceAudioTextAlignmentModelArchitecture.AUTO, description="Model architecture.")
    actions: List[AudioTextAlignmentModelActionConfig] = Field(default_factory=list)
