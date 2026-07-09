from typing import Literal, Optional, List
from pydantic import Field
from mindor.dsl.schema.common.model.tool import ModelTool
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonChatCompletionModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.CHAT_COMPLETION]
    tools: Optional[List[ModelTool]] = Field(default=None, description="Catalog of tools this component exposes for tool calling.")
