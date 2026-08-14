from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class ComponentJobConfig(OutputJobConfig):
    type: Literal[JobType.COMPONENT]
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run, given as a component ID or an inline component config.")
    action: str = Field(default="__default__", description="ID of the action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input payload passed to the component action.")
    repeat_count: Union[int, str] = Field(default=1, description="Number of times to repeat the component execution; must be at least 1.")

    @field_validator("repeat_count")
    def validate_repeat_count(cls, value):
        if isinstance(value, int) and value < 1:
            raise ValueError("'repeat_count' must be at least 1")
        return value
