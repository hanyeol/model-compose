from __future__ import annotations

from typing import Literal, List, Any
from pydantic import Field, field_validator
from .common import CommonJobConfig
from .types import JobType

class FanOutJobConfig(CommonJobConfig):
    type: Literal[JobType.FAN_OUT]
    input: Any = Field(..., description="Value fanned out to each branch; stream inputs are pumped, non-stream inputs are shared by reference.")
    output: List[str] = Field(..., min_length=1, description="Branch names; each is exposed as `${jobs.<id>.output.<name>}`.")
    buffer_size: int = Field(default=32, ge=1, description="Per-branch bounded queue depth used when the input is a stream.")
    spool: bool = Field(default=False, description="Spool a non-copyable StreamResource input to a temporary file so branches can consume at independent paces without queue backpressure.")

    @field_validator("output")
    def validate_branch_names(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("'output' branch names must be unique")
        return value
