from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import field_validator
from mindor.dsl.schema.action import CommonActionConfig
from mindor.dsl.schema.common.operator.condition import ConditionOperator
from .types import JobType

class JobRetryBackoff(str, Enum):
    FIXED       = "fixed"
    EXPONENTIAL = "exponential"

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

class JobRetryConfig(BaseModel):
    max_attempt_count: int = Field(default=1, description="Total attempts including the first, before falling through to on_error.")
    delay: Union[str, float] = Field(default=0.0, description="Base delay between attempts (duration string like '1s' or seconds).")
    backoff: JobRetryBackoff = Field(default=JobRetryBackoff.FIXED, description="How the delay grows across attempts.")
    max_delay: Optional[Union[str, float]] = Field(default=None, description="Cap for the delay after backoff is applied.")

    @field_validator("max_attempt_count")
    def validate_max_attempt_count(cls, value):
        if value < 1:
            raise ValueError("'max_attempt_count' must be at least 1")
        return value

class JobOnErrorConfig(BaseModel):
    output: Optional[Any] = Field(default=None, description="Fallback output rendered on failure. `${error.message}` is available.")
    to: Optional[str] = Field(default=None, description="Job ID to route to on failure.")

class CommonJobConfig(BaseModel):
    id: str = Field(default="__job__", description="ID of job.")
    name: Optional[str] = Field(default=None, description="Human-readable label for this job.")
    type: JobType = Field(..., description="Type of job.")
    max_run_count: int = Field(default=5, gt=0, description="Max executions per workflow run, including routing re-runs.")
    depends_on: List[str] = Field(default_factory=list, description="Jobs that must complete before this job runs.")
    interrupt: Optional[JobInterruptsConfig] = Field(default=None, description="Human-in-the-Loop interrupt points around each job run.")
    hook: Optional[JobHooksConfig] = Field(default=None, description="Inline Python hooks to run before/after each job run.")
    retry: Optional[JobRetryConfig] = Field(default=None, description="Retry policy applied to this job on failure.")
    on_error: Optional[JobOnErrorConfig] = Field(default=None, description="Fallback behavior after retries are exhausted.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Job id cannot be '__default__'")
        return value

    @field_validator("retry", mode="before")
    def normalize_retry(cls, value):
        if isinstance(value, int):
            return { "max_attempt_count": value }
        return value

    @field_validator("on_error", mode="before")
    def normalize_on_error(cls, value):
        if isinstance(value, str):
            if value.lower() != "ignore":
                raise ValueError(f"on_error string form must be 'ignore', got '{value}'")
            return {}
        return value

    def get_routing_jobs(self) -> Set[str]:
        jobs: Set[str] = set()
        if self.on_error and self.on_error.to:
            jobs.add(self.on_error.to)
        return jobs

class OutputJobConfig(CommonJobConfig):
    output: Optional[Any] = Field(default=None, description="Output data returned from this job.")
