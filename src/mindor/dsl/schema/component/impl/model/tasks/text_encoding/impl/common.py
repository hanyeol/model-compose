from typing import Literal, Optional
from pydantic import Field
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextEncodingModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_ENCODING]
    chat_template: Optional[str] = Field(default=None, description="Inline Jinja chat template string, overriding the tokenizer default.")
