from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerQueueDriver(str, Enum):
    REDIS = "redis"

class CommonControllerQueueConfig(BaseModel):
    driver: ControllerQueueDriver = Field(..., description="Queue backend driver.")
    name: str = Field(default="controller-queue", description="Base name for task queues.")
    timeout: int = Field(default=0, ge=0, description="Maximum time in seconds to wait for a result from the queue. 0 means no limit.")
