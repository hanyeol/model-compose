from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.utils.enum import enum_union_to_str

class ControllerRuntimeSpecs:
    def __init__(
        self,
        controller: ControllerConfig,
        components: Dict[str, ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: Dict[str, WorkflowConfig]
    ):
        self.controller: ControllerConfig = controller
        self.components: Dict[str, ComponentConfig] = components
        self.listeners: List[ListenerConfig] = listeners
        self.gateways: List[GatewayConfig] = gateways
        self.workflows: Dict[str, WorkflowConfig] = workflows

    def generate_native_runtime_specs(self) -> Dict[str, Any]:
        specs: Dict[str, Any] = {}

        specs["controller"] = self.controller.model_dump()
        specs["controller"]["runtime"] = "native"

        if getattr(self.controller.webui, "server_dir", None):
            specs["controller"]["webui"]["server_dir"] = "webui/server"

        if getattr(self.controller.webui, "static_dir", None):
            specs["controller"]["webui"]["static_dir"] = "webui/static"

        specs["components"] = {}
        for id, component in self.components.items():
            specs["components"][id] = component.model_dump()
            specs["components"][id]["runtime"] = "native"

        specs["listeners"] = [ listener.model_dump() for listener in self.listeners ]
        specs["gateways" ] = [ gateway.model_dump()  for gateway  in self.gateways  ]
        specs["workflows"] = { id: workflow.model_dump() for id, workflow in self.workflows.items() }

        return enum_union_to_str(specs)
