from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig, VllmEngineOptionsConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
