from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator
from .common import ListenerType, CommonListenerConfig

class HttpTriggerConfig(BaseModel):
    path: str = Field(..., description="URL path for this trigger endpoint.")
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(default="POST", description="HTTP method this trigger endpoint will accept.")
    bulk: Union[bool, str] = Field(default=False, description="Whether this trigger handles multiple items in a single request.")
    item: Optional[str] = Field(default=None, description="Field path to extract individual items from the trigger payload.")
    workflow: str = Field(..., description="Workflow ID to execute when this endpoint is triggered.")
    input: Optional[Dict[str, str]] = Field(default=None, description="Workflow input parameters.")

class HttpTriggerListenerConfig(CommonListenerConfig):
    type: Literal[ListenerType.HTTP_TRIGGER]
    host: str = Field(default="0.0.0.0", description="Host address to bind the HTTP server to.")
    port: int = Field(default=8091, ge=1, le=65535, description="Port number on which the HTTP server will listen.")
    base_path: Optional[str] = Field(default=None, description="Base path prefix for all trigger endpoints.")
    triggers: List[HttpTriggerConfig] = Field(default_factory=list, description="List of trigger endpoint configurations.")

    @model_validator(mode="before")
    def inflate_single_trigger(cls, values: Dict[str, Any]):
        if "triggers" not in values:
            trigger_keys = set(HttpTriggerConfig.model_fields.keys()) - set(CommonListenerConfig.model_fields.keys())
            if any(k in values for k in trigger_keys):
                values["triggers"] = [ { k: values.pop(k) for k in trigger_keys if k in values } ]
        return values
