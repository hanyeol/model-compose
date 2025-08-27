from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator

from .controller import ControllerConfig
from .component import ComponentConfig
from .listener import ListenerConfig
from .gateway import GatewayConfig
from .workflow import WorkflowConfig
from .logger import LoggerConfig

class ComposeConfig(BaseModel):
    controller: ControllerConfig
    components: List[ComponentConfig] = Field(default_factory=list, description="List of reusable components that define API calls, model tasks, or other operations")
    listeners: List[ListenerConfig] = Field(default_factory=list, description="List of listeners for handling asynchronous responses from external services.")
    gateways: List[GatewayConfig] = Field(default_factory=list, description="List of gateway services for tunneling local endpoints to public.")
    workflows: List[WorkflowConfig] = Field(default_factory=list, description="List of workflows that define sequences of jobs and their execution flow.")
    loggers: List[LoggerConfig] = Field(default_factory=list, description="List of logger configurations for capturing and storing execution logs.")

    @model_validator(mode="before")
    def inflate_single_component(cls, values: Dict[str, Any]):
        if "components" not in values:
            component_values = values.pop("component", None)
            if component_values:
                values["components"] = [ component_values ]
        return values
    
    @model_validator(mode="before")
    def inflate_single_listener(cls, values: Dict[str, Any]):
        if "listeners" not in values:
            listener_values = values.pop("listener", None)
            if listener_values:
                values["listeners"] = [ listener_values ]
        return values

    @model_validator(mode="before")
    def inflate_single_gateway(cls, values: Dict[str, Any]):
        if "gateways" not in values:
            gateways_values = values.pop("gateway", None)
            if gateways_values:
                values["gateways"] = [ gateways_values ]
        return values

    @model_validator(mode="before")
    def inflate_single_workflow(cls, values: Dict[str, Any]):
        if "workflows" not in values:
            workflow_values = values.pop("workflow", None)
            if workflow_values:
                values["workflows"] = [ workflow_values ]
        return values

    @model_validator(mode="before")
    def inflate_single_logger(cls, values: Dict[str, Any]):
        if "loggers" not in values:
            loggers_values = values.pop("logger", None)
            if loggers_values:
                values["loggers"] = [ loggers_values ]
        return values
