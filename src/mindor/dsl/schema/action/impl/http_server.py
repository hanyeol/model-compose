from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.http import HttpEventStreamFormat
from .common import CommonActionConfig

class HttpServerCompletionType(str, Enum):
    POLLING  = "polling"
    CALLBACK = "callback"

class HttpServerCommonCompletionConfig(BaseModel):
    type: HttpServerCompletionType
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")

class HttpServerPollingCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.POLLING]
    path: Optional[str] = Field(default=None, description="URL path for the polling endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method for polling completion status.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers for polling requests.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body for polling requests.")
    params: Dict[str, Any] = Field(default_factory=dict, description="URL query parameters for polling requests.")
    status: Optional[str] = Field(default=None, description="Field path to check for completion status in polling response.")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values indicating successful completion.")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values indicating failed completion.")
    interval: Union[str, int, float] = Field(default="5s", description="Interval between polling attempts.")
    timeout: Union[str, int, float] = Field(default="300s", description="Maximum wait time before giving up.")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpServerCallbackCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.CALLBACK]
    wait_for: Optional[str] = Field(default=None, description="Callback identifier to wait for in async completion mode.")

HttpServerCompletionConfig = Annotated[ 
    Union[
        HttpServerPollingCompletionConfig,
        HttpServerCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="URL path for this endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method this endpoint accepts.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers included in responses.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Default response body template.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Expected URL query parameters.")
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")
    completion: Optional[HttpServerCompletionConfig] = Field(default=None, description="Async request completion handling via polling or callbacks.")
