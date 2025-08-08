from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.action import TranslationModelActionConfig
from .common import CommonModelComponentConfig, ModelTaskType

class TranslationModelComponentConfig(CommonModelComponentConfig):
    task: Literal[ModelTaskType.TRANSLATION]
    actions: Dict[str, TranslationModelActionConfig] = Field(default_factory=dict)
