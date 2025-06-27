from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import ListenerType

class CommonListenerConfig(BaseModel):
    type: ListenerType
    runtime: Literal[ "docker", "native" ] = "native"
    max_concurrent_count: int = 0
