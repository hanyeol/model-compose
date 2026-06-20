from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextGenerationModelArchitecture(str, Enum):
    CAUSAL  = "causal"
    SEQ2SEQ = "seq2seq"

class HuggingfaceTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)
    architecture: HuggingfaceTextGenerationModelArchitecture = Field(default=HuggingfaceTextGenerationModelArchitecture.CAUSAL, description="Model architecture.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
