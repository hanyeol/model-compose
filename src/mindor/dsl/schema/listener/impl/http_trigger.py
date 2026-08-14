from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpTriggerConfig(BaseModel):
    path: str = Field(..., description="URL path appended to the listener base path for this trigger endpoint.")
    method: Literal[ "GET", "POST", "PUT", "DELETE", "PATCH" ] = Field(default="POST", description="HTTP method accepted by this trigger endpoint.")
    bulk: Union[bool, str] = Field(default=False, description="Whether this trigger accepts multiple items per request.")
    item: Optional[str] = Field(default=None, description="Field path used to extract individual items from a bulk payload.")
    workflow: str = Field(..., description="ID of the workflow executed when this trigger fires.")
    input: Optional[Dict[str, str]] = Field(default=None, description="Workflow input parameters mapped from the incoming request.")

class HttpTriggerListenerConfig(CommonListenerConfig):
    type: Literal[ListenerType.HTTP_TRIGGER]
    host: str = Field(default="0.0.0.0", description="Host address the trigger HTTP server binds to.")
    port: int = Field(default=8091, ge=1, le=65535, description="TCP port the trigger HTTP server listens on.")
    base_path: Optional[str] = Field(default=None, description="URL path prefix applied to every trigger endpoint.")
    triggers: List[HttpTriggerConfig] = Field(default_factory=list, description="Trigger endpoints exposed by this listener.")

    @model_validator(mode="before")
    def inflate_single_trigger(cls, values: Dict[str, Any]):
        if "triggers" not in values:
            trigger_keys = set(HttpTriggerConfig.model_fields.keys()) - set(CommonListenerConfig.model_fields.keys())
            if any(k in values for k in trigger_keys):
                values["triggers"] = [ { k: values.pop(k) for k in trigger_keys if k in values } ]
        return values
