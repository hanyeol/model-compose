from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import HuggingfaceSpeechToTextModelActionConfig
from .common import CommonSpeechToTextModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceSpeechToTextModelArchitecture(str, Enum):
    AUTO    = "auto"
    WHISPER = "whisper"

class HuggingfaceSpeechToTextModelComponentConfig(CommonSpeechToTextModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    architecture: HuggingfaceSpeechToTextModelArchitecture = Field(default=HuggingfaceSpeechToTextModelArchitecture.AUTO, description="Model architecture family; \"auto\" infers from the model config.")
    actions: List[HuggingfaceSpeechToTextModelActionConfig] = Field(default_factory=list, description="Actions this speech-to-text component exposes to workflows.")
