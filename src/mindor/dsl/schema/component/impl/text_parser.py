from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextParserActionConfig
from .common import ComponentType, CommonComponentConfig

class TextParserComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TEXT_PARSER]
    actions: List[TextParserActionConfig] = Field(default_factory=list)
