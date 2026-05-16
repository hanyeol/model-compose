from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerQueueDriver(str, Enum):
    REDIS = "redis"

class CommonControllerQueueConfig(BaseModel):
    driver: ControllerQueueDriver = Field(..., description="Queue backend driver.")
    name: str = Field(default="controller-queue", description="Base name for task queues.")
    timeout: Union[str, int, float] = Field(default="0s", description="Maximum time to wait for a result from the queue (e.g. '30s', '5m'). '0s' means no limit.")
