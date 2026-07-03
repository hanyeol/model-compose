from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from ..common import CommonChatCompletionModelComponentConfig
from .impl.common import ChatCompletionModelFamily
from ....common import ModelDriver

class CustomChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: ChatCompletionModelFamily = Field(..., description="Model family.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
