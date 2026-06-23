from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver
from ...vllm_common import VllmEngineOptions

class VllmChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig, VllmEngineOptions):
    driver: Literal[ModelDriver.VLLM] = Field(default=ModelDriver.VLLM)
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
