from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonKeyValueGetActionConfig,
    CommonKeyValueSetActionConfig,
    CommonKeyValueDeleteActionConfig,
    CommonKeyValueExistsActionConfig
)

class RedisKeyValueGetActionConfig(CommonKeyValueGetActionConfig):
    pass

class RedisKeyValueSetActionConfig(CommonKeyValueSetActionConfig):
    pass

class RedisKeyValueDeleteActionConfig(CommonKeyValueDeleteActionConfig):
    pass

class RedisKeyValueExistsActionConfig(CommonKeyValueExistsActionConfig):
    pass

RedisKeyValueStoreActionConfig = Annotated[
    Union[
        RedisKeyValueGetActionConfig,
        RedisKeyValueSetActionConfig,
        RedisKeyValueDeleteActionConfig,
        RedisKeyValueExistsActionConfig,
    ],
    Field(discriminator="method")
]
