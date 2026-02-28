from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from .common import LanguageModelComponentConfig, ModelTaskType

class TextClassificationModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_CLASSIFICATION]
    labels: Optional[List[str]] = Field(default=None, description="List of text classification labels.")
    actions: List[TextClassificationModelActionConfig] = Field(default_factory=list)
