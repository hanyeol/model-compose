from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class ComponentJobConfig(OutputJobConfig):
    type: Literal[JobType.COMPONENT]
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run. String identifier or full config object.")
    action: str = Field(default="__default__", description="Action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the component.")
    repeat_count: Union[int, str] = Field(default=1, description="Number of times to repeat component execution. Must be >= 1.")

    @field_validator("repeat_count")
    def validate_repeat_count(cls, value):
        if isinstance(value, int) and value < 1:
            raise ValueError("'repeat_count' must be at least 1")
        return value
