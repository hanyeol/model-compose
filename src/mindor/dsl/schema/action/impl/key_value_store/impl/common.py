from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from ...common import CommonActionConfig

class KeyValueStoreActionMethod(str, Enum):
    GET    = "get"
    SET    = "set"
    DELETE = "delete"
    EXISTS = "exists"

class CommonKeyValueStoreActionConfig(CommonActionConfig):
    method: KeyValueStoreActionMethod = Field(..., description="Key-value store operation method.")

class CommonKeyValueGetActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.GET]
    key: str = Field(..., description="Key to retrieve.")

class CommonKeyValueSetActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.SET]
    key: str = Field(..., description="Key to store.")
    value: Any = Field(..., description="Value to store.")
    ttl: Optional[Union[int, str]] = Field(default=None, description="Time-to-live in seconds. None = no expiry.")

class CommonKeyValueDeleteActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.DELETE]
    key: str = Field(..., description="Key to delete.")

class CommonKeyValueExistsActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.EXISTS]
    key: str = Field(..., description="Key to check existence.")
