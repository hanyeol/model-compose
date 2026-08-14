from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.http import HttpEventStreamFormat
from .common import CommonActionConfig

class HttpClientCompletionType(str, Enum):
    POLLING  = "polling"
    CALLBACK = "callback"

class HttpClientCommonCompletionConfig(BaseModel):
    type: HttpClientCompletionType
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")
    stream_fragmented: bool = Field(default=True, description="Whether the stream carries a single logical result split into pieces (e.g., LLM token deltas) rather than independent events.")

class HttpClientPollingCompletionConfig(HttpClientCommonCompletionConfig):
    type: Literal[HttpClientCompletionType.POLLING]
    endpoint: Optional[str] = Field(default=None, description="Full URL of the polling endpoint.")
    path: Optional[str] = Field(default=None, description="URL path appended to the base URL for polling requests.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method used for the polling request.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with the polling request.")
    body: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Request body sent with the polling request; accepts a JSON object, array, or raw string.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters sent with the polling request.")
    status: Optional[str] = Field(default=None, description="Field path in the polling response used to determine completion status.")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate successful completion.")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate failed completion.")
    interval: Optional[Union[str, int, float]] = Field(default=None, description="Delay between successive polling attempts.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum time to wait for polling completion before failing.")

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both")
        return values

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpClientCallbackCompletionConfig(HttpClientCommonCompletionConfig):
    type: Literal[HttpClientCompletionType.CALLBACK]
    wait_for: Optional[str] = Field(default=None, description="Callback identifier this request waits on for asynchronous completion.")

HttpClientCompletionConfig = Annotated[ 
    Union[
        HttpClientPollingCompletionConfig,
        HttpClientCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpClientActionConfig(CommonActionConfig):
    endpoint: Optional[str] = Field(default=None, description="Full URL of the request. Mutually exclusive with `path`.")
    path: Optional[str] = Field(default=None, description="URL path appended to the base URL. Mutually exclusive with `endpoint`.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method used for the request.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers sent with the request.")
    body: Optional[Union[Dict[str, Any], List[Any], str]] = Field(default=None, description="Request body; accepts a JSON object, JSON array, or raw string.")
    params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters appended to the request URL.")
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")
    stream_fragmented: bool = Field(default=True, description="Whether the stream carries a single logical result split into pieces (e.g., LLM token deltas) rather than independent events.")
    completion: Optional[HttpClientCompletionConfig] = Field(default=None, description="Handling for asynchronous request completion via polling or callbacks.")

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both")
        return values
