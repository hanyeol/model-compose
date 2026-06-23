from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import TextGenerationModelActionConfig
from .common import CommonTextGenerationModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmTextGenerationModelComponentConfig(CommonTextGenerationModelComponentConfig, VllmEngineOptionsConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[TextGenerationModelActionConfig] = Field(default_factory=list)
