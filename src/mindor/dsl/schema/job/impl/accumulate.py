from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import Field, field_validator, model_validator
from .common import JobType, OutputJobConfig

class AccumulateJobConfig(OutputJobConfig):
    type: Literal[JobType.ACCUMULATE]
    input: Any = Field(..., description="Source of items to iterate over; accepts a list or iterable.")
    accumulator: Optional[Any] = Field(default=None, description="Initial value folded across iterations.")
    do: "InlineJobConfig" = Field(..., description="Job executed for each item; its output becomes the next iteration's accumulator.")

    @field_validator("do", mode="before")
    def inflate_default_do_type(cls, value):
        if isinstance(value, dict) and "type" not in value:
            value["type"] = JobType.COMPONENT.value
        return value

    @model_validator(mode="after")
    def validate_inline_job(self):
        if getattr(self.do, "depends_on", None):
            raise ValueError("Inline `do` job cannot declare 'depends_on'.")
        return self
