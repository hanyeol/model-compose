from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class ForEachDoConfig(BaseModel):
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run for each item. String identifier or full config object.")
    action: str = Field(default="__default__", description="Action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the component for each item.")
    output: Optional[Any] = Field(default=None, description="Output data returned from each iteration.")

class ForEachJobConfig(OutputJobConfig):
    type: Literal[JobType.FOR_EACH]
    input: Any = Field(..., description="Source of items to iterate over. Accepts a list, async stream, or iterable.")
    batch_size: Optional[int] = Field(default=None, description="Items processed concurrently per batch. Defaults to 1.")
    streaming: bool = Field(default=False, description="If true, yield results as they complete instead of accumulating into a list.")
    do: ForEachDoConfig = Field(..., description="Component invocation to execute for each item.")
