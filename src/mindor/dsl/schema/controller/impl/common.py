from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.runtime import RuntimeType
from .types import ControllerType
from .webui import ControllerWebUIConfig

class CommonControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None)
    type: ControllerType = Field(..., description="")
    runtime: RuntimeType = Field(default=RuntimeType.NATIVE)
    max_concurrent_count: int = Field(default=1)
    threaded: bool = Field(default=False)
    webui: Optional[ControllerWebUIConfig] = Field(default=None)
