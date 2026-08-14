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
    operator: ConditionOperator = Field(default=ConditionOperator.EQ, description="Operator used to compare `input` against `value`.")
    input: Optional[Any] = Field(default=None, description="Value to evaluate against the condition.")
    value: Optional[Any] = Field(default=None, description="Value the input is compared against.")

class JobInterruptConfig(BaseModel):
    condition: Optional[JobInterruptConditionConfig] = Field(default=None, description="Condition that must match for the interrupt to fire; always fires when omitted.")
    message: Optional[str] = Field(default=None, description="Message shown to the client when the interrupt fires.")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Structured metadata delivered to the client alongside the interrupt.")

class JobInterruptsConfig(BaseModel):
    before: Union[bool, JobInterruptConfig] = Field(default=False, description="Whether to interrupt execution before the job runs.")
    after: Union[bool, JobInterruptConfig] = Field(default=False, description="Whether to interrupt execution after the job runs.")

    @field_validator("before", "after", mode="before")
    def normalize_interrupt(cls, value):
        if value is True:
            return JobInterruptConfig()
        if value is False or value is None:
            return False
        return value

class JobHookConfig(BaseModel):
    script: str = Field(..., description="Inline Python source defining a `hook` function to invoke.")

class JobHooksConfig(BaseModel):
    before: List[JobHookConfig] = Field(default_factory=list, description="Hooks executed before the job runs; accepts a single hook or a list.")
    after: List[JobHookConfig] = Field(default_factory=list, description="Hooks executed after the job runs; accepts a single hook or a list.")

    @field_validator("before", "after", mode="before")
    def normalize_hooks(cls, value):
        if isinstance(value, dict):
            return [ value ]
        return value

class JobRetryConfig(BaseModel):
    max_attempt_count: int = Field(default=1, description="Total number of attempts including the first before falling through to `on_error`.")
    delay: Union[str, float] = Field(default=0.0, description="Base delay between retry attempts, as a duration string (e.g., '1s') or seconds.")
    backoff: JobRetryBackoff = Field(default=JobRetryBackoff.FIXED, description="Growth pattern applied to the retry delay across attempts.")
    max_delay: Optional[Union[str, float]] = Field(default=None, description="Upper bound applied to the retry delay after backoff.")

    @field_validator("max_attempt_count")
    def validate_max_attempt_count(cls, value):
        if value < 1:
            raise ValueError("'max_attempt_count' must be at least 1")
        return value

class JobOnErrorConfig(BaseModel):
    output: Optional[Any] = Field(default=None, description="Fallback output rendered when the job fails; `${error.message}` is available.")
    to: Optional[str] = Field(default=None, description="ID of the job to route to when this job fails.")

class CommonJobConfig(BaseModel):
    id: str = Field(default="__job__", description="ID of job.")
    name: Optional[str] = Field(default=None, description="Human-readable label for the job.")
    type: JobType = Field(..., description="Type of job.")
    max_run_count: int = Field(default=25, gt=0, description="Maximum executions of this job per workflow run, including re-runs from routing.")
    depends_on: List[Union[List[str], str]] = Field(default_factory=list, description="IDs of jobs that must complete before this job runs.")
    interrupt: Optional[JobInterruptsConfig] = Field(default=None, description="Human-in-the-loop interrupt points around each run of the job.")
    hook: Optional[JobHooksConfig] = Field(default=None, description="Inline Python hooks executed before and after each run of the job.")
    retry: Optional[JobRetryConfig] = Field(default=None, description="Retry policy applied when the job fails.")
    on_error: Optional[JobOnErrorConfig] = Field(default=None, description="Fallback behavior applied after retries are exhausted.")

    @field_validator("id")
    def validate_id(cls, value):
        if value == "__default__":
            raise ValueError("Job id cannot be '__default__'")
        return value

    @field_validator("depends_on")
    def validate_depends_on(cls, value):
        for item in value:
            if isinstance(item, list) and not item:
                raise ValueError("'depends_on' cannot contain an empty group")
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
    output: Optional[Any] = Field(default=None, description="Output mapping that transforms and extracts values from the job's result.")
