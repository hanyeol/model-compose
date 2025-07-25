from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.runtime import RuntimeConfig
from .types import ControllerType
from .webui import ControllerWebUIConfig

class CommonControllerConfig(BaseModel):
    name: Optional[str] = Field(default=None)
    type: ControllerType = Field(..., description="")
    runtime: RuntimeConfig = Field(..., description="")
    max_concurrent_count: int = Field(default=1, description="")
    threaded: bool = Field(default=False, description="")
    webui: Optional[ControllerWebUIConfig] = Field(default=None, description="")

    @model_validator(mode="before")
    def inflate_runtime(cls, values: Dict[str, Any]):
        runtime = values.get("runtime")
        if runtime is None or isinstance(runtime, str):
            values["runtime"] = { "type": runtime or "native" }
        return values
