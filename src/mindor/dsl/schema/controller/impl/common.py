from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .types import ControllerType
from .webui import ControllerWebUIConfig

class CommonControllerConfig(BaseModel):
    name: Optional[str] = None
    type: ControllerType
    runtime: Literal[ "docker", "native" ] = "native"
    max_concurrent_count: int = 1
    threaded: bool = False
    webui: Optional[ControllerWebUIConfig] = None
