from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.logger import LoggerConfig
from .base import ControllerService, ControllerRegistry, TaskStatus

def create_controller(
    config: ControllerConfig,
    workflows: List[WorkflowConfig],
    components: List[ComponentConfig],
    listeners: List[ListenerConfig],
    gateways: List[GatewayConfig],
    loggers: List[LoggerConfig],
    daemon: bool
) -> ControllerService:
    try:
        if not ControllerRegistry:
            from . import services
        return ControllerRegistry[config.type](config, workflows, components, listeners, gateways, loggers, daemon)
    except KeyError:
        raise ValueError(f"Unsupported controller type: {config.type}")
