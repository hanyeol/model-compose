from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriverType
from ...base.sglang import SglangEngineOptionsConfig

class SglangTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriverType.SGLANG] = Field(default=ModelDriverType.SGLANG)
    options: Optional[SglangEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to SGLang when loading the model.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list, description="Actions this text generation component exposes to workflows.")
