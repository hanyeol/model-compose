from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpCallbackConfig(BaseModel):
    path: str = Field(..., description="URL path appended to the listener base path for this callback endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method accepted by this callback endpoint.")
    bulk: Union[bool, str] = Field(default=False, description="Whether this callback accepts multiple items per request.")
    item: Optional[str] = Field(default=None, description="Field path used to extract individual items from a bulk payload.")
    identify_by: Optional[str] = Field(default=None, description="Field path used to match a callback payload to a pending request.")
    status: Optional[str] = Field(default=None, description="Field path within the payload used to determine completion status.")
    success_when: Optional[List[str]] = Field(default=None, description="Status codes or values that mark the callback as successful.")
    fail_when: Optional[List[str]] = Field(default=None, description="Status codes or values that mark the callback as failed.")
    result: Optional[Any] = Field(default=None, description="Field path or transformation used to extract the final result from the payload.")

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), str):
                values[key] = [ values[key] ]
        return values

class HttpCallbackListenerConfig(CommonListenerConfig):
    type: Literal[ListenerType.HTTP_CALLBACK]
    host: str = Field(default="0.0.0.0", description="Host address the callback HTTP server binds to.")
    port: int = Field(default=8090, ge=1, le=65535, description="TCP port the callback HTTP server listens on.")
    base_path: Optional[str] = Field(default=None, description="URL path prefix applied to every callback endpoint.")
    callbacks: List[HttpCallbackConfig] = Field(default_factory=list, description="Callback endpoints exposed by this listener.")

    @model_validator(mode="before")
    def inflate_single_callback(cls, values: Dict[str, Any]):
        if "callbacks" not in values:
            callback_keys = set(HttpCallbackConfig.model_fields.keys()) - set(CommonListenerConfig.model_fields.keys())
            if any(k in values for k in callback_keys):
                values["callbacks"] = [ { k: values.pop(k) for k in callback_keys if k in values } ]
        return values
