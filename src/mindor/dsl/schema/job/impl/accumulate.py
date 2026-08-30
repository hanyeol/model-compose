from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class AccumulateDoConfig(BaseModel):
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run for each item, given as a component ID or an inline component config.")
    action: str = Field(default="__default__", description="ID of the action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input passed to the component action. Reference `${accumulator}` for the value carried over from the previous iteration, and `${item}` for the current item.")
    output: Optional[Any] = Field(default=None, description="Output mapping applied to each iteration's result; the mapped value becomes the next iteration's `${accumulator}`.")

class AccumulateJobConfig(OutputJobConfig):
    type: Literal[JobType.ACCUMULATE]
    input: Any = Field(..., description="Source of items to iterate over; accepts a list or iterable.")
    accumulator: Optional[Any] = Field(default=None, description="Value folded across iterations; exposed as `${accumulator}` and replaced by each iteration's output.")
    do: AccumulateDoConfig = Field(..., description="Component invocation executed for each item; its output becomes the next iteration's `${accumulator}`.")
