from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.runtime import RuntimeType
from .types import ListenerType

class CommonListenerConfig(BaseModel):
    type: ListenerType = Field(..., description="Type of listener.")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE, description="Runtime environment in which this listener executes.")
    max_concurrent_count: int = Field(default=0, description="Maximum concurrent incoming requests this listener handles; 0 means unbounded.")
