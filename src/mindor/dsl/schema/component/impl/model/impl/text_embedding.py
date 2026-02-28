from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import LanguageModelComponentConfig, ModelTaskType

class TextEmbeddingModelComponentConfig(LanguageModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_EMBEDDING]
    actions: List[TextEmbeddingModelActionConfig] = Field(default_factory=list)
