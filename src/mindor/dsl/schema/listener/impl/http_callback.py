from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpCallbackConfig(BaseModel):
    path: str
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method this callback endpoint will accept.")
    bulk: bool = Field(default=False, description="Whether this callback handles multiple items in a single request.")
    item: Optional[str] = Field(default=None, description="Field path to extract individual items from the callback payload.")
    identify_by: Optional[str] = Field(default=None, description="Field path used to identify and match callback responses to pending requests.")
    status: Optional[str] = Field(default=None, description="Field path to check for completion status in callback payload.")
    success_when: Optional[List[str]] = Field(default=None, description="Status codes or values that indicate successful completion.")
    fail_when: Optional[List[str]] = Field(default=None, description="Status codes or values that indicate failed completion.")
    result: Optional[Any] = Field(default=None, description="Field path or transformation to extract the final result from callback payload.")

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
    base_path: Optional[str] = Field(default=None, description="Base path prefix for all callback endpoints.")
    callbacks: List[HttpCallbackConfig] = Field(default_factory=list, description="List of callback endpoint configurations.")

    @model_validator(mode="before")
    def inflate_single_callback(cls, values: Dict[str, Any]):
        if "callbacks" not in values:
            callback_keys = set(HttpCallbackConfig.model_fields.keys()) - set(CommonListenerConfig.model_fields.keys())
            if any(k in values for k in callback_keys):
                values["callbacks"] = [ { k: values.pop(k) for k in callback_keys if k in values } ]
        return values
