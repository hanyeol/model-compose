from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator, field_validator
from .common import JobType, CommonJobConfig
from datetime import datetime

class WaitJobType(str, Enum):
    TIME_INTERVAL = "time-interval"
    SPECIFIC_TIME = "specific-time"

class CommonWaitJobConfig(CommonJobConfig):
    type: Literal[JobType.WAIT]
    mode: WaitJobType

class TimeIntervalWaitJobConfig(CommonWaitJobConfig):
    mode: Literal[WaitJobType.TIME_INTERVAL]
    duration: Union[str, float, int] = Field(..., description="Time to wait before continuing.")

class SpecificTimeWaitJobConfig(CommonWaitJobConfig):
    mode: Literal[WaitJobType.SPECIFIC_TIME]
    time: Union[datetime, str] = Field(..., description="Specific date and time to wait until.")
    timezone: Optional[str] = Field(default=None, description="")

WaitJobConfig = Annotated[
    Union[ 
        TimeIntervalWaitJobConfig,
        SpecificTimeWaitJobConfig
    ],
    Field(discriminator="mode")
]
