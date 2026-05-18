from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextTokenizerActionConfig
from .common import CommonTokenizerComponentConfig, TokenizerTaskType

class TextTokenizerComponentConfig(CommonTokenizerComponentConfig):
    task: Literal[TokenizerTaskType.TEXT]
    actions: List[TextTokenizerActionConfig] = Field(default_factory=list)
