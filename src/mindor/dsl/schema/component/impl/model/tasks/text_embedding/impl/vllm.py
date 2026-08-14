from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    options: Optional[VllmEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to vLLM when loading the model.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this text embedding component exposes to workflows.")
