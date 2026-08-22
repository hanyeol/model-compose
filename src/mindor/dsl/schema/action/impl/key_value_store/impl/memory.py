from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonKeyValueGetActionConfig,
    CommonKeyValueSetActionConfig,
    CommonKeyValueDeleteActionConfig,
    CommonKeyValueExistsActionConfig
)

class MemoryKeyValueGetActionConfig(CommonKeyValueGetActionConfig):
    pass

class MemoryKeyValueSetActionConfig(CommonKeyValueSetActionConfig):
    pass

class MemoryKeyValueDeleteActionConfig(CommonKeyValueDeleteActionConfig):
    pass

class MemoryKeyValueExistsActionConfig(CommonKeyValueExistsActionConfig):
    pass

MemoryKeyValueStoreActionConfig = Annotated[
    Union[
        MemoryKeyValueGetActionConfig,
        MemoryKeyValueSetActionConfig,
        MemoryKeyValueDeleteActionConfig,
        MemoryKeyValueExistsActionConfig,
    ],
    Field(discriminator="method")
]
