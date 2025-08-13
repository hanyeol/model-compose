from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.runtime import RuntimeType
from .types import ComponentType

class CommonComponentConfig(BaseModel):
    id: str = Field(default="__default__", description="ID of component.")
    type: ComponentType = Field(..., description="Type of component.")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE, description="Runtime environment used to execute this component.")
    max_concurrent_count: int = Field(default=1, description="Maximum number of concurrent actions this component can handle.")
    default: bool = Field(default=False, description="Whether to use this component when no component is explicitly specified.")
    actions: List[CommonActionConfig] = Field(default_factory=list, description="Actions available within this component.")
