from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class ForEachDoConfig(BaseModel):
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run for each item, given as a component ID or an inline component config.")
    action: str = Field(default="__default__", description="ID of the action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input payload passed to the component action for each item.")
    output: Optional[Any] = Field(default=None, description="Output mapping applied to each iteration's result.")

class ForEachJobConfig(OutputJobConfig):
    type: Literal[JobType.FOR_EACH]
    input: Any = Field(..., description="Source of items to iterate over; accepts a list, async stream, or iterable.")
    batch_size: Optional[int] = Field(default=None, description="Number of items processed concurrently per batch.")
    streaming: bool = Field(default=False, description="Whether results are yielded as they complete instead of accumulated into a list.")
    do: ForEachDoConfig = Field(..., description="Component invocation executed for each item.")
