from typing import Literal, Union, Optional, List, Annotated
from pydantic import Field
from mindor.dsl.schema.action import TadaTextToSpeechModelActionConfig
from ...common import CommonTextToSpeechModelComponentConfig
from .common import TextToSpeechModelFamily
from .....common import ModelDriver, HuggingfaceModelConfig, LocalModelConfig

_DEFAULT_ALLOW_PATTERNS = [ "*.safetensors", "*.json", "*.txt", "*.bin", "*.model" ]

class TadaTextToSpeechHuggingfaceModelConfig(HuggingfaceModelConfig):
    allow_patterns: Optional[List[str]] = Field(default=_DEFAULT_ALLOW_PATTERNS, description="Glob patterns selecting which TADA weight files to download from the repository snapshot.")

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
    model: TadaTextToSpeechModelConfig = Field(..., description="TADA model identifier — a HuggingFace repo ID or a local path.")
    tokenizer: str = Field(default="unsloth/Llama-3.2-1B", description="HuggingFace repository ID of the Llama tokenizer used by TADA.")
    actions: List[TadaTextToSpeechModelActionConfig] = Field(default_factory=list, description="Actions this text-to-speech component exposes to workflows.")
