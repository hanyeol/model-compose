from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from mindor.dsl.schema.transport.http import HttpStreamFormat
from .common import CommonActionConfig

class HttpServerCompletionType(str, Enum):
    POLLING  = "polling"
    CALLBACK = "callback"

class HttpServerCommonCompletionConfig(BaseModel):
    type: HttpServerCompletionType
    stream_format: Optional[HttpStreamFormat] = Field(default=None, description="Format of stream payload.")

class HttpServerPollingCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.POLLING]
    path: Optional[str] = Field(default=None, description="URL path for the polling endpoint to check completion status.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="HTTP method for polling completion status.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers to include in polling requests.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Request body data for polling requests.")
    params: Dict[str, str] = Field(default_factory=dict, description="URL query parameters for polling requests.")
    status: Optional[str] = Field(default=None, description="Field path to check for completion status in polling response.")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate successful completion.")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="Status codes or values that indicate failed completion.")
    interval: Optional[str] = Field(default=None, description="Time interval between polling attempts.")
    timeout: Optional[str] = Field(default=None, description="Maximum time to wait for completion before giving up.")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpServerCallbackCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.CALLBACK]
    wait_for: Optional[str] = Field(default=None, description="Callback identifier to wait for in asynchronous completion mode.")

HttpServerCompletionConfig = Annotated[ 
    Union[
        HttpServerPollingCompletionConfig,
        HttpServerCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None, description="URL path for this HTTP server endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method this endpoint will accept.")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers to include in responses from this endpoint.")
    body: Dict[str, Any] = Field(default_factory=dict, description="Default response body template for this endpoint.")
    params: Dict[str, str] = Field(default_factory=dict, description="Expected URL query parameters for this endpoint.")
    stream_format: Optional[HttpStreamFormat] = Field(default=None, description="Format of stream payload.")
    completion: Optional[HttpServerCompletionConfig] = Field(default=None, description="Configuration for handling asynchronous request completion via polling or callbacks.")
