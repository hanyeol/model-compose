from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, OutputJobConfig
from datetime import datetime

class DelayJobMode(str, Enum):
    TIME_INTERVAL = "time-interval"
    SPECIFIC_TIME = "specific-time"

class CommonDelayJobConfig(OutputJobConfig):
    type: Literal[JobType.DELAY]
    mode: DelayJobMode = Field(..., description="How the delay is expressed (e.g., time-interval, specific-time).")

class TimeIntervalDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.TIME_INTERVAL]
    duration: Union[float, int, str] = Field(..., description="Amount of time to wait before continuing, as a duration string (e.g., '30s') or seconds.")

class SpecificTimeDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.SPECIFIC_TIME]
    time: Union[datetime, str] = Field(..., description="Absolute date and time to wait until.")
    timezone: Optional[str] = Field(default=None, description="Timezone identifier used to interpret `time` (e.g., UTC, America/New_York).")

DelayJobConfig = Annotated[
    Union[ 
        TimeIntervalDelayJobConfig,
        SpecificTimeDelayJobConfig
    ],
    Field(discriminator="mode")
]
