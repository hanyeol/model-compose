from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver

class LlamaCppChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.LLAMACPP] = Field(default=ModelDriver.LLAMACPP)
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
