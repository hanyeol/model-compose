from typing import Union
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import field_validator
from .types import RuntimeType

class RuntimeRestartPolicy(str, Enum):
    NO         = "no"
    ON_FAILURE = "on-failure"
    ALWAYS     = "always"

class RuntimeRestartBackoff(str, Enum):
    FIXED       = "fixed"
    EXPONENTIAL = "exponential"

class RuntimeRestartConfig(BaseModel):
    policy: RuntimeRestartPolicy = Field(default=RuntimeRestartPolicy.NO, description="When to restart the worker after it exits.")
    max_attempt_count: int = Field(default=5, description="Total number of restart attempts within `window` before giving up; 0 means unlimited.")
    window: Union[str, float] = Field(default="10m", description="Window over which attempts are counted; the counter resets when the window elapses.")
    delay: Union[str, float] = Field(default="2s", description="Base delay before a restart attempt, as a duration string or seconds.")
    backoff: RuntimeRestartBackoff = Field(default=RuntimeRestartBackoff.EXPONENTIAL, description="Growth pattern applied to the restart delay across attempts.")
    max_delay: Union[str, float] = Field(default="60s", description="Upper bound applied to the restart delay after backoff.")

    @field_validator("max_attempt_count")
    def validate_max_attempt_count(cls, value):
        if value < 0:
            raise ValueError("'max_attempt_count' must be at least 0")
        return value

class CommonRuntimeConfig(BaseModel):
    type: RuntimeType = Field(..., description="Type of runtime.")
    restart: RuntimeRestartConfig = Field(default_factory=RuntimeRestartConfig, description="Policy applied when the worker exits.")

    @field_validator("restart", mode="before")
    def normalize_restart(cls, value):
        if isinstance(value, str):
            return { "policy": value }
        return value
