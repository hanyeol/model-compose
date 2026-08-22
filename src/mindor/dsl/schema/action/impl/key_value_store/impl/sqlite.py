from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from .common import (
    CommonKeyValueGetActionConfig,
    CommonKeyValueSetActionConfig,
    CommonKeyValueDeleteActionConfig,
    CommonKeyValueExistsActionConfig
)

class SqliteKeyValueGetActionConfig(CommonKeyValueGetActionConfig):
    pass

class SqliteKeyValueSetActionConfig(CommonKeyValueSetActionConfig):
    pass

class SqliteKeyValueDeleteActionConfig(CommonKeyValueDeleteActionConfig):
    pass

class SqliteKeyValueExistsActionConfig(CommonKeyValueExistsActionConfig):
    pass

SqliteKeyValueStoreActionConfig = Annotated[
    Union[
        SqliteKeyValueGetActionConfig,
        SqliteKeyValueSetActionConfig,
        SqliteKeyValueDeleteActionConfig,
        SqliteKeyValueExistsActionConfig,
    ],
    Field(discriminator="method")
]
