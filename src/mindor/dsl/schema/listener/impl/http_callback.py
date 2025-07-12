from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpCallbackConfig(BaseModel):
    path: str
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = "POST"
    bulk: bool = False
    item: Optional[str] = None
    identify_by: str
    status: Optional[str] = None
    success_when: Optional[List[str]] = None
    fail_when: Optional[List[str]] = None
    result: Optional[Any] = None

    @model_validator(mode="before")
    def normalize_status_fields(cls, values: Dict[str, Any]):
        for key in [ "success_when", "fail_when" ]:
            if isinstance(values.get(key), str):
                values[key] = [ values[key] ]
        return values

class HttpCallbackListenerConfig(CommonListenerConfig):
    type: Literal[ListenerType.HTTP_CALLBACK]
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8090)
    base_path: Optional[str] = Field(default=None)
    callbacks: List[HttpCallbackConfig] = Field(default_factory=list)

    @model_validator(mode="before")
    def inflate_single_callback(cls, values: Dict[str, Any]):
        if "callbacks" not in values:
            callback_keys = set(HttpCallbackConfig.model_fields.keys())
            if any(k in values for k in callback_keys):
                values["callbacks"] = [ { k: values.pop(k) for k in callback_keys if k in values } ]
        return values
