from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TadaTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver

class TadaTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.TADA]
    actions: List[TadaTextToSpeechModelActionConfig] = Field(default_factory=list)
    tokenizer_source: str = Field(
        default="unsloth/Llama-3.2-1B",
        description="HuggingFace repo to source the Llama tokenizer from (upstream default 'meta-llama/Llama-3.2-1B' is gated).",
    )
