from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriver
from ...base.llamacpp import LlamaCppEngineOptionsConfig

class LlamaCppTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriver.LLAMACPP] = Field(default=ModelDriver.LLAMACPP)
    options: Optional[LlamaCppEngineOptionsConfig] = Field(default=None, description="llama.cpp engine options.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
