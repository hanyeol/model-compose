from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field

class ControllerQueueDriver(str, Enum):
    REDIS = "redis"

class CommonControllerQueueConfig(BaseModel):
    driver: ControllerQueueDriver = Field(..., description="Queue backend driver.")
    name: str = Field(default="controller-queue", description="Base name for task queues.")
    timeout: Union[str, int, float] = Field(default="0s", description="Maximum time to wait for a result from the queue (e.g. '30s', '5m'). '0s' means no limit; subscribers must consume within blob_ttl or task fails with BlobNotFoundError.")
    max_blob_size: Optional[Union[str, int]] = Field(default="50M", description="Maximum size for a single binary payload transmitted via the queue (e.g. '512K', '50M', '2G'). Set to null for no limit. Exceeding values cause the task to fail with BlobTooLargeError.")
    blob_ttl: Optional[Union[str, int, float]] = Field(default=None, description="TTL for queue blob keys (e.g. '30s', '5m'). When unset, auto-derived as max(timeout * 2, 3600s). Must resolve to >= 1s.")
