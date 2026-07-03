from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    options: Optional[VllmEngineOptionsConfig] = Field(default=None, description="vLLM-specific engine options. Values set here override anything derived from the common fields.")
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
