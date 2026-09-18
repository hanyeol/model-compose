from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriverType

class HuggingfaceChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriverType.HUGGINGFACE]
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list, description="Actions this chat completion component exposes to workflows.")
