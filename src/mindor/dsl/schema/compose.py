from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator

from .controller import ControllerConfig
from .component import ComponentConfig
from .listener import ListenerConfig
from .gateway import GatewayConfig
from .workflow import WorkflowConfig

class ComposeConfig(BaseModel):
    controller: ControllerConfig
    components: Dict[str, ComponentConfig] = Field(default_factory=dict)
    listeners: List[ListenerConfig] = Field(default_factory=list)
    gateways: List[GatewayConfig] = Field(default_factory=list)
    workflows: Dict[str, WorkflowConfig] = Field(default_factory=dict)

    @model_validator(mode="before")
    def inflate_single_component(cls, values: Dict[str, Any]):
        if "components" not in values:
            component_values = values.pop("component", None)
            if component_values:
                values["components"] = { "__default__": component_values }
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
                values["workflows"] = { "__default__": workflow_values }
        return values
