from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver
from ...base.llamacpp import LlamaCppEngineOptionsConfig

class LlamaCppTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.LLAMACPP] = Field(default=ModelDriver.LLAMACPP)
    options: Optional[LlamaCppEngineOptionsConfig] = Field(default=None, description="llama.cpp engine options.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
