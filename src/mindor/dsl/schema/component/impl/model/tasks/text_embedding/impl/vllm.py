from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriverType
from ...base.vllm import VllmEngineOptionsConfig

class VllmTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.VLLM] = Field(default=ModelDriverType.VLLM)
    options: Optional[VllmEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to vLLM when loading the model.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this text embedding component exposes to workflows.")
