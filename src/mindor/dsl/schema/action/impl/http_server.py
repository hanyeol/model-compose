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
    path: Optional[str] = Field(default=None, description="")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET", description="")
    headers: Dict[str, str] = Field(default_factory=dict, description="")
    body: Dict[str, Any] = Field(default_factory=dict, description="")
    params: Dict[str, str] = Field(default_factory=dict, description="")
    status: Optional[str] = Field(default=None, description="")
    success_when: Optional[List[Union[int, str]]] = Field(default=None, description="")
    fail_when: Optional[List[Union[int, str]]] = Field(default=None, description="")
    interval: Optional[str] = Field(default=None, description="")
    timeout: Optional[str] = Field(default=None, description="")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpServerCallbackCompletionConfig(HttpServerCommonCompletionConfig):
    type: Literal[HttpServerCompletionType.CALLBACK]
    wait_for: Optional[str] = Field(default=None, description="")

HttpServerCompletionConfig = Annotated[ 
    Union[
        HttpServerPollingCompletionConfig,
        HttpServerCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpServerActionConfig(CommonActionConfig):
    path: Optional[str] = Field(default=None)
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="")
    headers: Dict[str, str] = Field(default_factory=dict, description="")
    body: Dict[str, Any] = Field(default_factory=dict, description="")
    params: Dict[str, str] = Field(default_factory=dict, description="")
    stream_format: Optional[HttpStreamFormat] = Field(default=None, description="Format of stream payload.")
    completion: Optional[HttpServerCompletionConfig] = Field(default=None, description="")
