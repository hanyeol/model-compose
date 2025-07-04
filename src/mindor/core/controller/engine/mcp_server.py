from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from mindor.dsl.schema.controller import McpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.workflow.schema import WorkflowSchema, WorkflowVariableConfig, create_workflow_schema
from .base import ControllerEngine, ControllerType, ControllerEngineMap
from mcp.server.fastmcp.server import FastMCP
import uvicorn

class WorkflowToolGenerator():
    def generate(self, workflow_id: str, workflow: WorkflowSchema, runner: Callable[[Optional[str], Any], Awaitable[Any]]) -> Tuple[Callable[[Any], Awaitable[Any]], str]:
        async def _run_workflow(input: Any, workflow_id=workflow_id) -> Any:
            return await runner(workflow_id, input)
        
        async def _build_input_value(*arguments, variables=workflow.input) -> Any:
            return await self._build_input_value(arguments, variables)

        arguments = ",".join([ variable.name or "input" for variable in workflow.input ])
        code = f"async def _run_workflow_{workflow_id}({arguments}): return await _run_workflow(await _build_input_value({arguments}))"
        context = { "_run_workflow": _run_workflow, "_build_input_value": _build_input_value }
        exec(compile(code, f"<string>", "exec"), context)

        description = ""

        return (context[f"_run_workflow_{workflow_id}"], description)

    async def _build_input_value(self, arguments: List[Any], variables: List[WorkflowVariableConfig]) -> Any:
        if len(variables) == 1 and not variables[0].name:
            return arguments[0]

        input: Dict[str, Any] = {}
        
        for value, variable in zip(arguments, variables):
            type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
            input[variable.name] = await self._convert_input_value(value, type, subtype, format, variable.internal)

        return input

    async def _convert_input_value(self, value: Any, type: str, subtype: Optional[str], format: Optional[str], internal: bool) -> Any:
        if type in [ "image", "audio", "video", "file" ] and (not internal or not format):
            pass

        return value if value != "" else None

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

        self._configure_tools()

    def _configure_tools(self) -> None:
        schema = create_workflow_schema(self.workflows, self.components)

        for workflow_id, workflow in schema.items():
            fn, description = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow)
            self.app.add_tool(
                fn=fn,
                name=workflow.name or workflow_id,
                annotations=None,
                title=workflow.title,
                description=description
            )
    
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
