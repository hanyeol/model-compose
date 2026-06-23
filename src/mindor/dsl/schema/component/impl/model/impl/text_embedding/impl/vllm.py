from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver
from ...vllm_common import VllmEngineOptions

class VllmTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig, VllmEngineOptions):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
