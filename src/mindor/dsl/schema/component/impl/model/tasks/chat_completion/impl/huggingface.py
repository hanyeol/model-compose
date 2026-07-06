from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver

class HuggingfaceChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.HUGGINGFACE]
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
