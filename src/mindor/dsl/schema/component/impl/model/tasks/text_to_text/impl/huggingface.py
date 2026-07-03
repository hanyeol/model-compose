from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import TextToTextModelActionConfig
from .common import CommonTextToTextModelComponentConfig
from ...common import ModelDriver

class HuggingfaceTextToTextModelArchitecture(str, Enum):
    AUTO    = "auto"
    T5      = "t5"
    BART    = "bart"
    MARIAN  = "marian"
    PEGASUS = "pegasus"
    MBART   = "mbart"

class HuggingfaceTextToTextModelComponentConfig(CommonTextToTextModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE] = Field(default=ModelDriver.HUGGINGFACE)
    architecture: HuggingfaceTextToTextModelArchitecture = Field(default=HuggingfaceTextToTextModelArchitecture.AUTO, description="Model architecture.")
    actions: List[TextToTextModelActionConfig] = Field(default_factory=list)
