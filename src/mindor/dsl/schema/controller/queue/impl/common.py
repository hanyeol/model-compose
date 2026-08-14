from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerQueueDriver(str, Enum):
    REDIS = "redis"

class CommonControllerQueueConfig(BaseModel):
    driver: ControllerQueueDriver = Field(..., description="Backend implementation used for the controller task queue.")
    name: str = Field(default="controller-queue", description="Base name used for task queue keys.")
    timeout: Union[str, int, float] = Field(default="0s", description="Maximum seconds to wait for a queue result before failing; '0s' waits indefinitely.")
    max_blob_size: Optional[Union[str, int]] = Field(default="50M", description="Maximum size of a single binary payload transferred through the queue.")
    blob_ttl: Optional[Union[str, int, float]] = Field(default=None, description="Time-to-live applied to queue blob entries.")
