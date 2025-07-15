from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.runtime import RuntimeType
from .types import ComponentType

class CommonComponentConfig(BaseModel):
    type: ComponentType = Field(..., description="")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE)
    max_concurrent_count: int = Field(default=1)
    default: bool = Field(default=False)
    actions: Dict[str, CommonActionConfig] = Field(default_factory=dict)
