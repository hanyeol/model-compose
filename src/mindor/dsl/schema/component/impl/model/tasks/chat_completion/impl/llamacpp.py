from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriver
from ...base.llamacpp import LlamaCppEngineOptionsConfig

class LlamaCppChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriver.LLAMACPP] = Field(default=ModelDriver.LLAMACPP)
    options: Optional[LlamaCppEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to llama.cpp when loading the model.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list, description="Actions this chat completion component exposes to workflows.")
