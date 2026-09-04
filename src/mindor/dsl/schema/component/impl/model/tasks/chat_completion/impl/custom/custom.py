from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from ..common import CommonChatCompletionModelComponentConfig
from .common import ChatCompletionModelFamily
from ....common import ModelDriver

class CustomChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ChatCompletionModelFamily = Field(..., description="Model family selecting the custom chat completion implementation.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list, description="Actions this chat completion component exposes to workflows.")
