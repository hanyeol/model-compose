from typing import Optional, List, Any
from mindor.dsl.schema.controller import McpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.logger import LoggerConfig
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.tool import WorkflowToolGenerator, WorkflowTool
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.utils.streaming import StreamResource, Base64StreamResource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.utils.http_client import create_stream_with_url
from ..base import ControllerService, ControllerType, TaskState, register_controller
from mcp.server.fastmcp.server import FastMCP
from mcp.types import ContentBlock, TextContent, ImageContent, AudioContent
import uvicorn, json

@register_controller(ControllerType.MCP_SERVER)
class McpServerController(ControllerService):
    def __init__(
        self,
        config: McpServerControllerConfig,
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        loggers: List[LoggerConfig],
        daemon: bool
    ):
        super().__init__(config, workflows, components, listeners, gateways, loggers, daemon)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastMCP = FastMCP(self.config.name, **{
            "streamable_http_path": self.config.base_path or "/"
        })

        self._configure_tools()

    def _configure_tools(self) -> None:
        for workflow_id, workflow in self.workflow_schemas.items():
            tool = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow_as_tool)
            self.app.add_tool(
                fn=tool.fn,
                name=workflow.name or workflow_id,
                title=workflow.title,
                description=self._build_tool_description(tool),
                annotations=None
            )

    async def _run_workflow_as_tool(self, workflow_id: Optional[str], input: Any) -> List[ContentBlock]:
        state = await self.run_workflow(workflow_id, input, wait_for_completion=True)
        workflow = self.workflow_schemas[workflow_id]
        return await self._build_output_value(state, workflow)

    async def _build_output_value(self, state: TaskState, workflow: WorkflowSchema) -> List[ContentBlock]:
        output: List[ContentBlock] = []

        if state.output:
            if len(workflow.output) == 1 and not workflow.output[0].name:
                variable = workflow.output[0]
                output.append(await self._convert_output_value(state.output, variable.type, variable.subtype, variable.format))
            else:
                for variable in workflow.output:
                    output.append(await self._convert_output_value(state.output[variable.name], variable.type, variable.subtype, variable.format))

        return output

    async def _convert_output_value(self, value: Any, type: WorkflowVariableType, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> ContentBlock:
        if type in [ WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ]:
            if format == WorkflowVariableFormat.BASE64 and len(value) < 1024 * 1024: # at most 1MB
                if type == WorkflowVariableType.IMAGE:
                    return ImageContent(type="image", data=value, mimeType=f"{type}/{subtype}")
                if type == WorkflowVariableType.AUDIO:
                    return AudioContent(type="audio", data=value, mimeType=f"{type}/{subtype}")
            if not format or format not in [ WorkflowVariableFormat.PATH, WorkflowVariableFormat.URL ]:
                value = await self._save_value_to_temporary_file(value, subtype, format)
            return TextContent(type="text", text=value)

        if isinstance(value, (dict, list)):
            return TextContent(type="text", text=json.dumps(value))

        return TextContent(type="text", text=str(value))

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], format: Optional[WorkflowVariableFormat]) -> Optional[str]:
        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        return None

    def _build_tool_description(self, tool: WorkflowTool) -> str:
        lines = [tool.description or ""]

        if tool.parameters:
            lines.append("")
            lines.append("Args:")
            for param in tool.parameters:
                lines.append(f"    {param.name} ({param.type}): {param.description or ''}")

        return "\n".join(lines)

    async def _serve(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app.streamable_http_app(),
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        try:
            await self.server.serve()
        finally:
            self.server = None

    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True
