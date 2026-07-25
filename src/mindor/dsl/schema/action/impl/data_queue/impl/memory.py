from typing import Union, Annotated
from pydantic import Field
from .common import (
    CommonDataQueueEnqueueActionConfig,
    CommonDataQueueDequeueActionConfig,
)

class MemoryDataQueueEnqueueActionConfig(CommonDataQueueEnqueueActionConfig):
    pass

class MemoryDataQueueDequeueActionConfig(CommonDataQueueDequeueActionConfig):
    pass

MemoryDataQueueActionConfig = Annotated[
    Union[
        MemoryDataQueueEnqueueActionConfig,
        MemoryDataQueueDequeueActionConfig,
    ],
    Field(discriminator="method")
]
