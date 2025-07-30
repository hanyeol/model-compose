from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.runtime import RuntimeType
from .types import ListenerType

class CommonListenerConfig(BaseModel):
    type: ListenerType = Field(..., description="")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE, description="")
    max_concurrent_count: int = Field(default=0, description="")
