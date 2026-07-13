from typing import Union, Optional, List, Any, Literal
from enum import Enum
from pydantic import Field
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
    key: Union[str, List[str]] = Field(..., description="Key(s) to retrieve.")

class CommonKeyValueSetActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.SET]
    key: str = Field(..., description="Key to store.")
    value: Any = Field(..., description="Value to store.")
    ttl: Optional[Union[int, str]] = Field(default=None, description="Time-to-live in seconds. None = no expiry.")

class CommonKeyValueDeleteActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.DELETE]
    key: Union[str, List[str]] = Field(..., description="Key(s) to delete.")

class CommonKeyValueExistsActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.EXISTS]
    key: Union[str, List[str]] = Field(..., description="Key(s) to check for existence.")
