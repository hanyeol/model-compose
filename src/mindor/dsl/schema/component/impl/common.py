from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Callable, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.runtime import RuntimeConfig, RuntimeType
from .types import ComponentType

ComponentValidatorRegistry: Dict[Tuple[ComponentType, str], List[Callable[[Any], Any]]] = {}

class CommonComponentConfig(BaseModel):
    id: str = Field(default="__component__", description="ID of component.")
    type: ComponentType = Field(..., description="Type of component.")
    runtime: RuntimeConfig = Field(..., description="Runtime environment settings.")
    max_concurrent_count: int = Field(default=0, description="Maximum concurrent actions this component can handle.")
    default: bool = Field(default=False, description="Use this component when none is explicitly specified.")
    actions: List[CommonActionConfig] = Field(default_factory=list, description="Actions available within this component.")

    @model_validator(mode="before")
    def inflate_single_action(cls, values: Dict[str, Any]):
        if "actions" not in values:
            action_values = values.pop("action", None)
            if action_values:
                values["actions"] = [ action_values ]
        return values

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

def component_validator(type: ComponentType, mode: Literal[ "before", "after" ] = "before"):
    def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
        ComponentValidatorRegistry.setdefault((type, mode), []).append(func)
        return func
    return decorator

def apply_component_validators(component: Any, mode: Literal[ "before", "after" ]) -> None:
    type = component.get("type") if mode == "before" else component.type
    for func in ComponentValidatorRegistry.get((type, mode), []):
        func(component)
