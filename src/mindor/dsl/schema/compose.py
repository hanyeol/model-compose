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
    controller: ControllerConfig
    components: List[ComponentConfig] = Field(default_factory=list, description="Reusable components defining API calls, model tasks, or other operations.")
    listeners: List[ListenerConfig] = Field(default_factory=list, description="Listeners handling asynchronous responses from external services.")
    gateways: List[GatewayConfig] = Field(default_factory=list, description="Gateway services for tunneling local endpoints publicly.")
    systems: List[SystemConfig] = Field(default_factory=list, description="External systems managed alongside the controller lifecycle.")
    workflows: List[WorkflowConfig] = Field(default_factory=list, description="Workflows defining job sequences and execution flow.")
    tracers: List[TracerConfig] = Field(default_factory=list, description="Tracer configs for sending structured traces to external observability tools.")
    loggers: List[LoggerConfig] = Field(default_factory=list, description="Logger configs for capturing and storing execution logs.")

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
    def inflate_single_system(cls, values: Dict[str, Any]):
        if "systems" not in values:
            system_values = values.pop("system", None)
            if system_values:
                values["systems"] = [ system_values ]
        return values

    @model_validator(mode="before")
    def inflate_single_tracer(cls, values: Dict[str, Any]):
        if "tracers" not in values:
            tracer_values = values.pop("tracer", None)
            if tracer_values:
                values["tracers"] = [ tracer_values ]
        return values

    @model_validator(mode="before")
    def inflate_single_logger(cls, values: Dict[str, Any]):
        if "loggers" not in values:
            loggers_values = values.pop("logger", None)
            if loggers_values:
                values["loggers"] = [ loggers_values ]
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
