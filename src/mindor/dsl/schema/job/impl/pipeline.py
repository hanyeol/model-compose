from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field, field_validator
from mindor.dsl.schema.component import ComponentConfig
from .common import JobType, OutputJobConfig

class PipelineStepConfig(BaseModel):
    component: Union[str, ComponentConfig] = Field(default="__default__", description="Component to run for this step, given as a component ID or an inline component config.")
    action: str = Field(default="__default__", description="ID of the action to invoke on the component.")
    input: Optional[Any] = Field(default=None, description="Input passed to the component action. Reference `${input}` for the pipeline input or `${output}` for the previous step's output.")
    output: Optional[Any] = Field(default=None, description="Output mapping applied to this step's result before it flows into the next step.")

class PipelineJobConfig(OutputJobConfig):
    type: Literal[JobType.PIPELINE]
    input: Optional[Any] = Field(default=None, description="Value exposed to the first step as `${input}`.")
    steps: List[PipelineStepConfig] = Field(..., min_length=1, description="Steps executed sequentially; each step's output becomes `${output}` for the next.")

    @field_validator("steps")
    def validate_steps_non_empty(cls, value):
        if not value:
            raise ValueError("'steps' must contain at least one step")

        return value
