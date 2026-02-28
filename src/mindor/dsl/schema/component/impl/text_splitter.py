from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextSplitterActionConfig
from .common import ComponentType, CommonComponentConfig

class TextSplitterComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TEXT_SPLITTER]
    actions: List[TextSplitterActionConfig] = Field(default_factory=list)
