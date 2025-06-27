from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import McpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from .base import ControllerEngine, ControllerType, ControllerEngineMap

class McpServerController(ControllerEngine):
    def __init__(
        self,
        config: McpServerControllerConfig,
        components: Dict[str, ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: Dict[str, WorkflowConfig],
        env: Dict[str, str],
        daemon: bool
    ):
        super().__init__(config, components, listeners, gateways, workflows, env, daemon)

    async def _serve(self) -> None:
        pass

    async def _shutdown(self) -> None:
        pass

ControllerEngineMap[ControllerType.MCP_SERVER] = McpServerController
