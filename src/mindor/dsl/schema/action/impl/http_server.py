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
    path: Optional[str] = Field(default=None, description="URL path exposed for polling completion status.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method accepted at the polling endpoint.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers included with polling responses.")
    body: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Default response body for polling requests; accepts a JSON object, array, or raw string.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Expected query parameters on polling requests.")
    status: Optional[str] = Field(default=None, description="Field path in the polling response used to determine completion status.")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate successful completion.")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate failed completion.")
    interval: Union[str, int, float] = Field(default="5s", description="Delay between successive polling attempts.")
    timeout: Union[str, int, float] = Field(default="300s", description="Maximum time to wait for polling completion before failing.")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpServerCallbackCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.CALLBACK]
    wait_for: Optional[str] = Field(default=None, description="Callback identifier this action waits on for asynchronous completion.")

HttpServerCompletionConfig = Annotated[ 
    Union[
        HttpServerPollingCompletionConfig,
        HttpServerCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="URL path exposed by this endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method this endpoint accepts.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers included in the response.")
    body: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Default response body template; accepts a JSON object, array, or raw string.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Expected query parameters on incoming requests.")
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")
    completion: Optional[HttpServerCompletionConfig] = Field(default=None, description="Handling for asynchronous request completion via polling or callbacks.")
