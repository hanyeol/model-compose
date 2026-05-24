from typing import Literal, Optional, List
from pydantic import Field
from ...common import LanguageModelComponentConfig, ModelTaskType

class CommonTextClassificationModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_CLASSIFICATION]
    labels: Optional[List[str]] = Field(default=None, description="List of text classification labels.")
