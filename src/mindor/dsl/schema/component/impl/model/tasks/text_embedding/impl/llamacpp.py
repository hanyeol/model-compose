from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver

class LlamaCppTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.LLAMACPP] = Field(default=ModelDriver.LLAMACPP)
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
