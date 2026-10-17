from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import SupertonicTextToSpeechModelActionConfig
from ..common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from ....common import ModelDriverType

class SupertonicTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriverType.CUSTOM] = Field(default=ModelDriverType.CUSTOM)
    family: Literal[TextToSpeechModelFamily.SUPERTONIC]
    actions: List[SupertonicTextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")
