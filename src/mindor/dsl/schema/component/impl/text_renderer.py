from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import TextRendererActionConfig
from .common import ComponentType, CommonComponentConfig

class TextRendererComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.TEXT_RENDERER]
    actions: List[TextRendererActionConfig] = Field(default_factory=list)
