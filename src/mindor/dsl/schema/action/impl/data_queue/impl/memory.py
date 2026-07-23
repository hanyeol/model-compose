from typing import Union, Annotated
from pydantic import Field
from .common import (
    CommonDataQueuePublishActionConfig,
    CommonDataQueueConsumeActionConfig,
)

class MemoryDataQueuePublishActionConfig(CommonDataQueuePublishActionConfig):
    pass

class MemoryDataQueueConsumeActionConfig(CommonDataQueueConsumeActionConfig):
    pass

MemoryDataQueueActionConfig = Annotated[
    Union[
        MemoryDataQueuePublishActionConfig,
        MemoryDataQueueConsumeActionConfig,
    ],
    Field(discriminator="method")
]
