from typing import Literal
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonChatCompletionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.CHAT_COMPLETION]
