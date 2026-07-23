from typing import Literal
from enum import Enum
from pydantic import Field
from ...common import CommonComponentConfig, ComponentType

class DataQueueDriver(str, Enum):
    MEMORY = "memory"

class CommonDataQueueComponentConfig(CommonComponentConfig):
    type: Literal[ComponentType.DATA_QUEUE]
    driver: DataQueueDriver = Field(..., description="Data queue backend driver.")
    max_size: int = Field(default=0, ge=0, description="Maximum number of items the queue can hold. 0 = unbounded.")
