from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriverType
from ...base.llamacpp import LlamaCppEngineOptionsConfig

class LlamaCppTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.LLAMACPP] = Field(default=ModelDriverType.LLAMACPP)
    options: Optional[LlamaCppEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to llama.cpp when loading the model.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list, description="Actions this text generation component exposes to workflows.")
