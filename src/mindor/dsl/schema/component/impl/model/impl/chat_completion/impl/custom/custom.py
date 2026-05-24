from typing import Literal, List
from enum import Enum
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from ..common import CommonChatCompletionModelComponentConfig
from ....common import ModelDriver

class CustomChatCompletionModelFamily(str, Enum):
    pass

class CustomChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.CUSTOM] = Field(default=ModelDriver.CUSTOM)
    family: CustomChatCompletionModelFamily = Field(..., description="Model family.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
