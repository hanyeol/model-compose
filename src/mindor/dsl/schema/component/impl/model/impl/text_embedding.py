from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextEmbeddingModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class TextEmbeddingModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_EMBEDDING]
    actions: Dict[str, TextEmbeddingModelActionConfig] = Field(default_factory=dict)
