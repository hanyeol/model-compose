from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig
from datetime import datetime

class DelayJobMode(str, Enum):
    TIME_INTERVAL = "time-interval"
    SPECIFIC_TIME = "specific-time"

class CommonDelayJobConfig(CommonJobConfig):
    type: Literal[JobType.DELAY]
    mode: DelayJobMode = Field(..., description="")

class TimeIntervalDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.TIME_INTERVAL]
    duration: Union[str, float, int] = Field(..., description="Time to wait before continuing.")

class SpecificTimeDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.SPECIFIC_TIME]
    time: Union[datetime, str] = Field(..., description="Specific date and time to wait until.")
    timezone: Optional[str] = Field(default=None, description="")

DelayJobConfig = Annotated[
    Union[ 
        TimeIntervalDelayJobConfig,
        SpecificTimeDelayJobConfig
    ],
    Field(discriminator="mode")
]
