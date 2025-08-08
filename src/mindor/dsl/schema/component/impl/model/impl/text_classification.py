from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TextClassificationModelActionConfig
from .common import ClassificationModelComponentConfig, ModelTaskType

class TextClassificationModelComponentConfig(ClassificationModelComponentConfig):
    task: Literal[ModelTaskType.TEXT_CLASSIFICATION]
    actions: Dict[str, TextClassificationModelActionConfig] = Field(default_factory=dict)
