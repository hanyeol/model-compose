from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from enum import Enum
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class HttpClientCompletionType(str, Enum):
    POLLING  = "polling"
    CALLBACK = "callback"

class HttpClientCommonCompletionConfig(BaseModel):
    type: HttpClientCompletionType

class HttpClientPollingCompletionConfig(HttpClientCommonCompletionConfig):
    type: Literal[HttpClientCompletionType.POLLING]
    endpoint: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="GET")
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, str] = Field(default_factory=dict)
    status: Optional[str] = Field(default=None)
    success_when: Optional[List[Union[int, str]]] = Field(default=None)
    fail_when: Optional[List[Union[int, str]]] = Field(default=None)
    interval: Optional[str] = Field(default=None)
    timeout: Optional[str] = Field(default=None)

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both.")
        return values

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), (int, str)):
                values[key] = [ values[key] ]
        return values

class HttpClientCallbackCompletionConfig(HttpClientCommonCompletionConfig):
    type: Literal[HttpClientCompletionType.CALLBACK]
    wait_for: str = Field(..., description="")

HttpClientCompletionConfig = Annotated[ 
    Union[
        HttpClientPollingCompletionConfig,
        HttpClientCallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpClientActionConfig(CommonActionConfig):
    endpoint: Optional[str] = Field(default=None)
    path: Optional[str] = Field(default=None)
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST")
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, str] = Field(default_factory=dict)
    completion: Optional[HttpClientCompletionConfig] = Field(default=None)

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both.")
        return values
