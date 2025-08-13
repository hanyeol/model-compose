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
        components: List[ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: List[WorkflowConfig]
    ):
        self.controller: ControllerConfig = controller
        self.components: List[ComponentConfig] = components
        self.listeners: List[ListenerConfig] = listeners
        self.gateways: List[GatewayConfig] = gateways
        self.workflows: List[WorkflowConfig] = workflows

    def generate_native_runtime_specs(self) -> Dict[str, Any]:
        specs: Dict[str, Any] = {}

        specs["controller"] = { **self.controller.model_dump(), "runtime": "native" }

        if getattr(self.controller.webui, "server_dir", None):
            specs["controller"]["webui"]["server_dir"] = "webui/server"

        if getattr(self.controller.webui, "static_dir", None):
            specs["controller"]["webui"]["static_dir"] = "webui/static"

        specs["components"] = [
            { **component.model_dump(), "runtime": "native" } for component in self.components
        ]

        specs["listeners"] = [ listener.model_dump() for listener in self.listeners ]
        specs["gateways" ] = [ gateway.model_dump()  for gateway  in self.gateways  ]
        specs["workflows"] = [ workflow.model_dump() for workflow in self.workflows ]

        return enum_union_to_str(specs)
