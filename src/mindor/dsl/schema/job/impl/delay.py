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
    mode: DelayJobMode = Field(..., description="Delay mode.")

class TimeIntervalDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.TIME_INTERVAL]
    duration: Union[float, int, str] = Field(..., description="Time to wait before continuing.")

class SpecificTimeDelayJobConfig(CommonDelayJobConfig):
    mode: Literal[DelayJobMode.SPECIFIC_TIME]
    time: Union[datetime, str] = Field(..., description="Specific date and time to wait until.")
    timezone: Optional[str] = Field(default=None, description="Timezone identifier used to interpret the 'time' field.")

DelayJobConfig = Annotated[
    Union[ 
        TimeIntervalDelayJobConfig,
        SpecificTimeDelayJobConfig
    ],
    Field(discriminator="mode")
]
