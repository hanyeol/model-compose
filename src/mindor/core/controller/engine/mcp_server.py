from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import McpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from .base import ControllerEngine, ControllerType, ControllerEngineMap
from mcp.server.fastmcp.server import FastMCP
import uvicorn

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

        self.server: Optional[uvicorn.Server] = None
        self.app: FastMCP = FastMCP(self.config.name, settings={
            "streamable_http_path": self.config.base_path
        })

    async def _serve(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app.streamable_http_app(),
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        await self.server.serve()

    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True

ControllerEngineMap[ControllerType.MCP_SERVER] = McpServerController
