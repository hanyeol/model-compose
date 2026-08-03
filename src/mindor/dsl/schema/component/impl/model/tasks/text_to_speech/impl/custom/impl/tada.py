from typing import Literal, Union, Optional, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import TadaTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_ALLOW_PATTERNS = [ "*.safetensors", "*.json", "*.txt", "*.bin", "*.model" ]

class TadaTextToSpeechHuggingfaceModelConfig(HuggingfaceModelConfig):
    allow_patterns: Optional[List[str]] = Field(default=_DEFAULT_ALLOW_PATTERNS, description="Files to include when downloading TADA weights.")

TadaTextToSpeechModelConfig = Annotated[
    Union[
        TadaTextToSpeechHuggingfaceModelConfig,
        LocalModelConfig
    ],
    Field(discriminator="provider")
]

class TadaTextToSpeechModelComponentConfig(CommonTextToSpeechModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: Literal[TextToSpeechModelFamily.TADA]
    model: TadaTextToSpeechModelConfig = Field(..., description="Model repository or local file path.")
    tokenizer: str = Field(default="unsloth/Llama-3.2-1B", description="HuggingFace repo of the Llama tokenizer.")
    actions: List[TadaTextToSpeechModelActionConfig] = Field(default_factory=list)
