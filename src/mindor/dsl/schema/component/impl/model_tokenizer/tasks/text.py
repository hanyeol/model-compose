from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextModelTokenizerActionConfig
from .common import CommonModelTokenizerComponentConfig, ModelTokenizerTaskType

class TextModelTokenizerComponentConfig(CommonModelTokenizerComponentConfig):
    task: Literal[ModelTokenizerTaskType.TEXT]
    actions: List[TextModelTokenizerActionConfig] = Field(default_factory=list)
