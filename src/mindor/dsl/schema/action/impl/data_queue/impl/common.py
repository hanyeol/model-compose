from typing import Literal, Optional, Any, Union
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class DataQueueActionMethod(str, Enum):
    ENQUEUE = "enqueue"
    DEQUEUE = "dequeue"

class CommonDataQueueActionConfig(CommonActionConfig):
    method: DataQueueActionMethod = Field(..., description="Data queue operation method.")
    session: Optional[str] = Field(default=None, description="Key that isolates items into an independent sub-queue. Omit to use the shared default queue.")

class CommonDataQueueEnqueueActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.ENQUEUE]
    item: Union[Any, str] = Field(..., description="Value to enqueue.")
    spread: Union[bool, str] = Field(default=False, description="If true, enqueue each element of a list or iterator item separately.")

class CommonDataQueueDequeueActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.DEQUEUE]
