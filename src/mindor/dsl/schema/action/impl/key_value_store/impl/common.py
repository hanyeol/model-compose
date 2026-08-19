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
    method: KeyValueStoreActionMethod = Field(..., description="Key-value store operation this action performs.")

class CommonKeyValueGetActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.GET]
    key: Union[str, List[str]] = Field(..., description="Key or list of keys to retrieve from the store.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input keys processed per batch.")

class CommonKeyValueSetActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.SET]
    key: Union[str, List[str]] = Field(..., description="Key or list of keys under which the value is stored.")
    value: Any = Field(..., description="Value written to the store.")
    ttl: Optional[Union[int, str]] = Field(default=None, description="Time-to-live in seconds; unset means no expiry.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input entries processed per batch.")

class CommonKeyValueDeleteActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.DELETE]
    key: Union[str, List[str]] = Field(..., description="Key or list of keys to delete from the store.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input keys processed per batch.")

class CommonKeyValueExistsActionConfig(CommonKeyValueStoreActionConfig):
    method: Literal[KeyValueStoreActionMethod.EXISTS]
    key: Union[str, List[str]] = Field(..., description="Key or list of keys whose existence is checked.")
    batch_size: Optional[Union[int, str]] = Field(default=None, description="Number of input keys processed per batch.")
