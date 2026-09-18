from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from pydantic import BaseModel, Field
from pydantic import model_validator

from .controller import ControllerConfig
from .component import ComponentConfig
from .component.impl.common import apply_component_validators
from .listener import ListenerConfig
from .gateway import GatewayConfig
from .system import SystemConfig
from .workflow import WorkflowConfig
from .tracer import TracerConfig
from .logger import LoggerConfig

class ComposeConfig(BaseModel):
    controller: ControllerConfig = Field(..., description="Controller that hosts workflows and exposes them to clients.")
    components: List[ComponentConfig] = Field(default_factory=list, description="Reusable components that define API calls, model tasks, and other operations.")
    listeners: List[ListenerConfig] = Field(default_factory=list, description="Listeners that receive asynchronous responses from external services.")
    gateways: List[GatewayConfig] = Field(default_factory=list, description="Gateways that expose local endpoints through public tunnels.")
    systems: List[SystemConfig] = Field(default_factory=list, description="External systems managed alongside the controller lifecycle.")
    workflows: List[WorkflowConfig] = Field(default_factory=list, description="Workflows that define ordered job sequences and their execution flow.")
    tracers: List[TracerConfig] = Field(default_factory=list, description="Tracers that emit structured traces to external observability tools.")
    loggers: List[LoggerConfig] = Field(default_factory=list, description="Loggers that capture and store execution logs.")

    @model_validator(mode="before")
    def inflate_single_component(cls, values: Dict[str, Any]):
        if "components" not in values:
            component = values.pop("component", None)
            if component:
                values["components"] = [ component ]
        return values

    @model_validator(mode="before")
    def inflate_single_listener(cls, values: Dict[str, Any]):
        if "listeners" not in values:
            listener = values.pop("listener", None)
            if listener:
                values["listeners"] = [ listener ]
        return values

    @model_validator(mode="before")
    def inflate_single_gateway(cls, values: Dict[str, Any]):
        if "gateways" not in values:
            gateway = values.pop("gateway", None)
            if gateway:
                values["gateways"] = [ gateway ]
        return values

    @model_validator(mode="before")
    def inflate_single_workflow(cls, values: Dict[str, Any]):
        if "workflows" not in values:
            workflow = values.pop("workflow", None)
            if workflow:
                values["workflows"] = [ workflow ]
        return values

    @model_validator(mode="before")
    def inflate_single_system(cls, values: Dict[str, Any]):
        if "systems" not in values:
            system = values.pop("system", None)
            if system:
                values["systems"] = [ system ]
        return values

    @model_validator(mode="before")
    def inflate_single_tracer(cls, values: Dict[str, Any]):
        if "tracers" not in values:
            tracer = values.pop("tracer", None)
            if tracer:
                values["tracers"] = [ tracer ]
        return values

    @model_validator(mode="before")
    def inflate_single_logger(cls, values: Dict[str, Any]):
        if "loggers" not in values:
            logger = values.pop("logger", None)
            if logger:
                values["loggers"] = [ logger ]
        return values

    @model_validator(mode="before")
    def apply_component_before_validators(cls, values: Dict[str, Any]):
        if "components" in values:
            for component in values["components"]:
                apply_component_validators(component, mode="before")
        if "component" in values:
            apply_component_validators(values["component"], mode="before")
        return values

    @model_validator(mode="after")
    def apply_component_after_validators(self):
        for component in self.components:
            apply_component_validators(component, mode="after")
        return self
