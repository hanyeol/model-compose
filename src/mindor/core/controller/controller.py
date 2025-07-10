from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from .engine import ControllerEngine, ControllerEngineMap

def create_controller(
    config: ControllerConfig, 
    components: Dict[str, ComponentConfig],
    listeners: List[ListenerConfig],
    gateways: List[GatewayConfig],
    workflows: Dict[str, WorkflowConfig],
    daemon: bool
) -> ControllerEngine:
    try:
        return ControllerEngineMap[config.type](config, components, listeners, gateways, workflows, daemon)
    except KeyError:
        raise ValueError(f"Unsupported controller type: {config.type}")
