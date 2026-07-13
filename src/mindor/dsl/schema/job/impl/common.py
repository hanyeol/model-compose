from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import field_validator
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .types import JobType

class JobInterruptConditionConfig(BaseModel):
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Condition operator.")
    input: Optional[Any] = Field(default=None, description="Input to evaluate.")
    value: Optional[Any] = Field(default=None, description="Value to compare against.")

class JobInterruptConfig(BaseModel):
    condition: Optional[JobInterruptConditionConfig] = Field(default=None, description="Condition for the interrupt to fire. If omitted, always interrupts.")
    message: Optional[str] = Field(default=None, description="Message displayed to the user when interrupted.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Structured metadata to pass to the client on interrupt.")

class JobInterruptsConfig(BaseModel):
    before: Union[bool, JobInterruptConfig] = Field(default=False, description="Interrupt before the job runs.")
    after: Union[bool, JobInterruptConfig] = Field(default=False, description="Interrupt after the job runs.")

    @field_validator("before", "after", mode="before")
    def normalize_interrupt(cls, value):
        if value is True:
            return JobInterruptConfig()
        if value is False or value is None:
            return False
        return value

class JobHookConfig(BaseModel):
    script: str = Field(..., description="Inline Python defining a `hook` function.")

class JobHooksConfig(BaseModel):
    before: List[JobHookConfig] = Field(default_factory=list, description="Hook(s) to run before the job runs. Accepts a single hook or a list.")
    after: List[JobHookConfig] = Field(default_factory=list, description="Hook(s) to run after the job runs. Accepts a single hook or a list.")

    @field_validator("before", "after", mode="before")
    def normalize_hooks(cls, value):
        if isinstance(value, dict):
            return [ value ]
        return value

class CommonJobConfig(BaseModel):
    id: str = Field(default="__job__", description="ID of job.")
    name: Optional[str] = Field(default=None, description="Human-readable label for this job.")
    type: JobType = Field(..., description="Type of job.")
    max_run_count: int = Field(default=5, gt=0, description="Max executions per workflow run, including routing re-runs.")
    depends_on: List[str] = Field(default_factory=list, description="Jobs that must complete before this job runs.")
    interrupt: Optional[JobInterruptsConfig] = Field(default=None, description="Human-in-the-Loop interrupt points around each job run.")
    hook: Optional[JobHooksConfig] = Field(default=None, description="Inline Python hooks to run before/after each job run.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Job id cannot be '__default__'")
        return value

    def get_routing_jobs(self) -> List[str]:
        return []

class OutputJobConfig(CommonJobConfig):
    output: Optional[Any] = Field(default=None, description="Output data returned from this job.")
