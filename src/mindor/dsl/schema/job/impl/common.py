from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator
from mindor.dsl.schema.action import CommonActionConfig
from .types import JobType

class CommonJobConfig(BaseModel):
    id: str = Field(default="__job__", description="ID of job.")
    name: Optional[str] = Field(default=None, description="Human-readable label for this job. Used as the group label in the web UI when this job's output is presented as a variable group.")
    type: JobType = Field(..., description="Type of job.")
    max_run_count: int = Field(default=5, gt=0, description="Maximum number of times this job may be executed within a single workflow run (including re-runs triggered by routing).")
    depends_on: List[str] = Field(default_factory=list, description="Jobs that must complete before this job runs.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Job id cannot be '__default__'")
        return value

    def get_routing_jobs(self) -> List[str]:
        return []

class OutputJobConfig(CommonJobConfig):
    output: Optional[Any] = Field(default=None, description="The output data returned from this job. Accepts any type.")
