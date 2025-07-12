from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import CommonActionConfig
from .types import ComponentType

class CommonComponentConfig(BaseModel):
    type: ComponentType
    runtime: Literal[ "docker", "native" ] = Field(default="native")
    max_concurrent_count: int = Field(default=1)
    default: bool = Field(default=False)
    actions: Dict[str, CommonActionConfig] = Field(default_factory=dict)
