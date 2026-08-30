from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import Field, field_validator, model_validator
from .common import JobType, OutputJobConfig

class PipelineJobConfig(OutputJobConfig):
    type: Literal[JobType.PIPELINE]
    input: Optional[Any] = Field(default=None, description="Initial input passed to the first step.")
    steps: List["InlineJobConfig"] = Field(..., min_length=1, description="Jobs executed sequentially; each step's output feeds the next.")

    @field_validator("steps", mode="before")
    def inflate_default_step_type(cls, value):
        if isinstance(value, list):
            for step in value:
                if isinstance(step, dict) and "type" not in step:
                    step["type"] = JobType.COMPONENT.value
        return value

    @field_validator("steps")
    def validate_steps_non_empty(cls, value):
        if not value:
            raise ValueError("'steps' must contain at least one step")
        return value

    @model_validator(mode="after")
    def validate_inline_jobs(self):
        for index, step in enumerate(self.steps):
            if getattr(step, "depends_on", None):
                raise ValueError(f"Inline pipeline step[{index}] cannot declare 'depends_on'.")
        return self
