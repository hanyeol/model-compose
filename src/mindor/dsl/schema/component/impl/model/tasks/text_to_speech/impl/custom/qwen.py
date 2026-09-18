from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from ....common import ModelDriverType

class QwenTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TextToSpeechModelFamily.QWEN]
    actions: List[TextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")
