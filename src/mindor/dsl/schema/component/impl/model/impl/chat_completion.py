from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import ChatCompletionModelActionConfig
from .common import LanguageModelComponentConfig, ModelTaskType

class ChatCompletionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.CHAT_COMPLETION]
    actions: List[ChatCompletionModelActionConfig] = Field(default_factory=list)
