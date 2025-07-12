from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import CommonActionConfig

class CommonCompletionConfig(BaseModel):
    type: Literal[ "polling", "callback" ]

class PollingCompletionConfig(CommonCompletionConfig):
    type: Literal["polling"]
    endpoint: Optional[str] = None
    path: Optional[str] = None
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = "GET"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, str] = Field(default_factory=dict)
    status: Optional[str] = None
    success_when: Optional[List[Union[int, str]]] = None
    fail_when: Optional[List[Union[int, str]]] = None
    interval: Optional[str] = None
    timeout: Optional[str] = None

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

class CallbackCompletionConfig(CommonCompletionConfig):
    type: Literal["callback"]
    wait_for: str

HttpClientCompletionConfig = Annotated[ 
    Union[
        PollingCompletionConfig,
        CallbackCompletionConfig
    ],
    Field(discriminator="type")
]

class HttpClientActionConfig(CommonActionConfig):
    endpoint: Optional[str] = None
    path: Optional[str] = None
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = "POST"
    headers: Dict[str, str] = Field(default_factory=dict)
    body: Dict[str, Any] = Field(default_factory=dict)
    params: Dict[str, str] = Field(default_factory=dict)
    completion: Optional[HttpClientCompletionConfig] = None

    @model_validator(mode="before")
    def validate_endpoint_or_path(cls, values: Dict[str, Any]):
        if bool(values.get("endpoint")) == bool(values.get("path")):
            raise ValueError("Either 'endpoint' or 'path' must be set, but not both.")
        return values
