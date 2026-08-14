from typing import Literal, Optional, Any, Union
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class DataQueueActionMethod(str, Enum):
    ENQUEUE = "enqueue"
    DEQUEUE = "dequeue"

class CommonDataQueueActionConfig(CommonActionConfig):
    method: DataQueueActionMethod = Field(..., description="Queue operation this action performs.")
    session: Optional[str] = Field(default=None, description="Key that isolates items into an independent sub-queue; omit to use the shared default queue.")

class CommonDataQueueEnqueueActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.ENQUEUE]
    item: Union[Any, str] = Field(..., description="Value appended to the queue.")
    spread: Union[bool, str] = Field(default=False, description="Whether to enqueue each element of a list or iterator item as a separate entry.")

class CommonDataQueueDequeueActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.DEQUEUE]
