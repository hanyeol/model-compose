from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonTextEmbeddingModelComponentConfig
from ...common import ModelDriverType
from ...base.sglang import SglangEngineOptionsConfig

class SglangTextEmbeddingModelComponentConfig(CommonTextEmbeddingModelComponentConfig):
    driver: Literal[ModelDriverType.SGLANG] = Field(default=ModelDriverType.SGLANG)
    options: Optional[SglangEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to SGLang when loading the model.")
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list, description="Actions this text embedding component exposes to workflows.")
