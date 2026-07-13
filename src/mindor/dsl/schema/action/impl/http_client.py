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

class HttpClientPollingCompletionConfig(HttpClientCommonCompletionConfig):
    type: Literal[HttpClientCompletionType.POLLING]
    endpoint: Optional[str] = Field(default=None, description="URL endpoint for polling requests.")
    path: Optional[str] = Field(default=None, description="URL path appended to base_url for polling.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method for polling requests.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers for polling requests.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body for polling requests.")
    params: Dict[str, Any] = Field(default_factory=dict, description="URL query parameters for polling requests.")
    status: Optional[str] = Field(default=None, description="Field path to check for completion status in polling response.")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values indicating successful completion.")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values indicating failed completion.")
    interval: Optional[Union[str, int, float]] = Field(default=None, description="Interval between polling attempts.")
    timeout: Optional[Union[str, int, float]] = Field(default=None, description="Maximum wait time before giving up.")

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
    wait_for: Optional[str] = Field(default=None, description="Callback identifier to wait for in async completion mode.")

HttpClientCompletionConfig = Annotated[ 
    Union[
        HttpClientPollingCompletionConfig,
        HttpClientCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpClientActionConfig(CommonActionConfig):
    endpoint: Optional[str] = Field(default=None, description="Full URL endpoint (mutually exclusive with path).")
    path: Optional[str] = Field(default=None, description="URL path appended to base_url (mutually exclusive with endpoint).")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method for the request.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers for the request.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body.")
    params: Dict[str, Any] = Field(default_factory=dict, description="URL query parameters.")
    stream_format: Optional[HttpEventStreamFormat] = Field(default=None, description="Encoding format applied to each chunk of the stream payload.")
    completion: Optional[HttpClientCompletionConfig] = Field(default=None, description="Async request completion handling via polling or callbacks.")

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both")
        return values
