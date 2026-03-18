from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.system import SystemConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.logger import LoggerConfig
from .base import ControllerService, TaskStatus

def create_controller(
    config: ControllerConfig,
    workflows: List[WorkflowConfig],
    components: List[ComponentConfig],
    systems: List[SystemConfig],
    listeners: List[ListenerConfig],
    gateways: List[GatewayConfig],
    loggers: List[LoggerConfig],
    daemon: bool
) -> ControllerService:
    return ControllerService(config, workflows, components, systems, listeners, gateways, loggers, daemon)
