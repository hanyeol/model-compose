from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class ForEachDoConfig(BaseModel):
    component: Union[str, ComponentConfig] = Field(default="__default__", description="The component to run for each item. May be either a string identifier or a full config object.")
    action: str = Field(default="__default__", description="The action to invoke on the component. Defaults to '__default__'.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the component for each item. Accepts any type.")
    output: Optional[Any] = Field(default=None, description="The output data returned from each iteration. Accepts any type.")

class ForEachJobConfig(OutputJobConfig):
    type: Literal[JobType.FOR_EACH]
    input: Any = Field(..., description="Source of items to iterate over. Accepts a list, an async stream, or any iterable value.")
    batch_size: Optional[int] = Field(default=None, description="Number of items processed concurrently per batch. Defaults to 1 (one item at a time).")
    do: ForEachDoConfig = Field(..., description="Component invocation to execute for each item.")
