from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, CommonJobConfig

class ActionJobConfig(CommonJobConfig):
    type: Literal[JobType.ACTION]
    component: Union[str, ComponentConfig] = Field(default="__default__", description="The component to run. May be either a string identifier or a full config object.")
    action: str = Field(default="__default__", description="The action to invoke on the component. Defaults to '__default__'.")
    input: Optional[Any] = Field(default=None, description="Input data supplied to the component. Accepts any type.")
    repeat_count: Union[int, str] = Field(default=1, description="Number of times to repeat the component execution. Must be at least 1.")

    @field_validator("repeat_count")
    def validate_repeat_count(cls, value):
        if isinstance(value, int) and value < 1:
            raise ValueError("'repeat_count' must be at least 1")
        return value
