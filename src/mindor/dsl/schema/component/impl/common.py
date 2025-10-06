from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.runtime import RuntimeConfig, RuntimeType
from .types import ComponentType

class CommonComponentConfig(BaseModel):
    id: str = Field(default="__component__", description="ID of component.")
    type: ComponentType = Field(..., description="Type of component.")
    runtime: RuntimeConfig = Field(..., description="Runtime environment settings.")
    max_concurrent_count: int = Field(default=1, description="Maximum number of concurrent actions this component can handle.")
    default: bool = Field(default=False, description="Whether to use this component when no component is explicitly specified.")
    actions: List[CommonActionConfig] = Field(default_factory=list, description="Actions available within this component.")

    @model_validator(mode="before")
    def inflate_runtime(cls, values: Dict[str, Any]):
        runtime = values.get("runtime")
        if runtime is None or isinstance(runtime, str):
            values["runtime"] = { "type": runtime or RuntimeType.NATIVE }
        return values

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Component id cannot be '__default__'")
        return value
