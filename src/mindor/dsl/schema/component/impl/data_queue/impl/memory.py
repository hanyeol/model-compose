from typing import Literal, List
from pydantic import Field
from mindor.dsl.schema.action import MemoryDataQueueActionConfig
from .common import CommonDataQueueComponentConfig, DataQueueDriver

class MemoryDataQueueComponentConfig(CommonDataQueueComponentConfig):
    driver: Literal[DataQueueDriver.MEMORY]
    actions: List[MemoryDataQueueActionConfig] = Field(default_factory=list)
