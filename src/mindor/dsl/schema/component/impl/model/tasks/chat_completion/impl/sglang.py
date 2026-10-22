from typing import Literal, List, Optional
from pydantic import Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import CommonChatCompletionModelComponentConfig
from ...common import ModelDriverType
from ...base.sglang import SglangEngineOptionsConfig

class SglangChatCompletionModelComponentConfig(CommonChatCompletionModelComponentConfig):
    driver: Literal[ModelDriverType.SGLANG] = Field(default=ModelDriverType.SGLANG)
    options: Optional[SglangEngineOptionsConfig] = Field(default=None, description="Engine options forwarded to SGLang when loading the model.")
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list, description="Actions this chat completion component exposes to workflows.")
