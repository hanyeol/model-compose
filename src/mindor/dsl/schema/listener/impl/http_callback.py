from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpCallbackConfig(BaseModel):
    path: str
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="")
    bulk: bool = Field(default=False, description="")
    item: Optional[str] = Field(default=None, description="")
    identify_by: Optional[str] = Field(default=None, description="")
    status: Optional[str] = Field(default=None, description="")
    success_when: Optional[List[str]] = Field(default=None, description="")
    fail_when: Optional[List[str]] = Field(default=None, description="")
    result: Optional[Any] = Field(default=None, description="")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), str):
                values[key] = [ values[key] ]
        return values

class HttpCallbackListenerConfig(CommonListenerConfig):
    type: Literal[ListenerType.HTTP_CALLBACK]
    host: str = Field(default="0.0.0.0", description="Host address to bind the HTTP server to.")
    port: int = Field(default=8090, description="Port number on which the HTTP server will listen.")
    base_path: Optional[str] = Field(default=None, description="")
    callbacks: List[HttpCallbackConfig] = Field(default_factory=list, description="")

    @model_validator(mode="before")
    def inflate_single_callback(cls, values: Dict[str, Any]):
        if "callbacks" not in values:
            callback_keys = set(HttpCallbackConfig.model_fields.keys()) - set(CommonListenerConfig.model_fields.keys())
            if any(k in values for k in callback_keys):
                values["callbacks"] = [ { k: values.pop(k) for k in callback_keys if k in values } ]
        return values
