from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.operator.condition import ConditionOperator
from .common import JobType, OutputJobConfig

class ComponentInterruptConditionConfig(BaseModel):
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Condition operator.")
    input: Optional[Any] = Field(default=None, description="Input to evaluate.")
    value: Optional[Any] = Field(default=None, description="Value to compare against.")

class ComponentInterruptPointConfig(BaseModel):
    condition: Optional[ComponentInterruptConditionConfig] = Field(default=None, description="Condition that must be true for the interrupt to fire. If omitted, always interrupts.")
    message: Optional[str] = Field(default=None, description="A message displayed to the user when the workflow is interrupted.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Structured metadata to pass to the client on interrupt.")

class ComponentInterruptConfig(BaseModel):
    before: Union[bool, ComponentInterruptPointConfig] = Field(default=False, description="Interrupt before the component executes. Set to true or provide {message, metadata}.")
    after: Union[bool, ComponentInterruptPointConfig] = Field(default=False, description="Interrupt after the component executes. Set to true or provide {message, metadata}.")

    @field_validator("before", "after", mode="before")
    def normalize_point(cls, value):
        if value is True:
            return ComponentInterruptPointConfig()
        if value is False or value is None:
            return False
        return value

class ComponentJobConfig(OutputJobConfig):
    type: Literal[JobType.COMPONENT]
    component: Union[str, ComponentConfig] = Field(default="__default__", description="The component to run. May be either a string identifier or a full config object.")
    action: str = Field(default="__default__", description="The action to invoke on the component. Defaults to '__default__'.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the component. Accepts any type.")
    interrupt: Optional[ComponentInterruptConfig] = Field(default=None, description="Configuration for Human-in-the-Loop interrupt points around component execution.")
    repeat_count: Union[int, str] = Field(default=1, description="Number of times to repeat the component execution. Must be at least 1.")

    @field_validator("repeat_count")
    def validate_repeat_count(cls, value):
        if isinstance(value, int) and value < 1:
            raise ValueError("'repeat_count' must be at least 1")
        return value
