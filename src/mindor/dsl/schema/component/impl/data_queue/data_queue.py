from typing import Union, Annotated, Dict, Any
from pydantic import Field
from ..common import component_validator, ComponentType
from .impl import *
from .impl.common import DataQueueDriver

DataQueueComponentConfig = Annotated[
    Union[
        MemoryDataQueueComponentConfig,
    ],
    Field(discriminator="driver")
]

@component_validator(ComponentType.DATA_QUEUE, mode="before")
def inflate_default_driver(values: Dict[str, Any]) -> Dict[str, Any]:
    if "driver" not in values:
        values["driver"] = DataQueueDriver.MEMORY
    return values
