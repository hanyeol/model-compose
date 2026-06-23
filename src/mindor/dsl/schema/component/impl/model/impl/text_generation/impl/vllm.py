from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriver
from ...vllm_common import VllmEngineOptions

class VllmTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig, VllmEngineOptions):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
