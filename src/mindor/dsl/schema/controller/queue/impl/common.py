from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerQueueDriver(str, Enum):
    REDIS = "redis"

class CommonControllerQueueConfig(BaseModel):
    driver: ControllerQueueDriver = Field(..., description="Queue backend driver.")
    name: str = Field(default="controller-queue", description="Base name for task queues.")
    timeout: Union[str, int, float] = Field(default="0s", description="Max wait for a queue result.")
    max_blob_size: Optional[Union[str, int]] = Field(default="50M", description="Max size of a single binary payload via the queue.")
    blob_ttl: Optional[Union[str, int, float]] = Field(default=None, description="TTL for queue blob keys.")
