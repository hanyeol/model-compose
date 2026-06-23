from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver
from ...base.vllm import VllmEngineOptionsConfig

class VllmChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig, VllmEngineOptionsConfig):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
