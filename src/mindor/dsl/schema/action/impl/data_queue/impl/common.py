from typing import Literal, Optional
from enum import Enum
from pydantic import Field
from ...common import CommonActionConfig

class DataQueueActionMethod(str, Enum):
    PUBLISH = "publish"
    CONSUME = "consume"

class CommonDataQueueActionConfig(CommonActionConfig):
    method: DataQueueActionMethod = Field(..., description="Data queue operation method.")
    session: Optional[str] = Field(default=None, description="Session key that isolates items into an independent sub-queue. Producers and consumers with the same session share a queue; items published under one session are never seen by consumers of another. Omit to use the shared default session.")

class CommonDataQueuePublishActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.PUBLISH]

class CommonDataQueueConsumeActionConfig(CommonDataQueueActionConfig):
    method: Literal[DataQueueActionMethod.CONSUME]
