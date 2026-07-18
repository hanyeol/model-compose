from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Set, Any
from mindor.dsl.schema.controller import McpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.controller.adapter.impl.mcp_server import McpServerTransport
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.tool import WorkflowToolGenerator, ResumeToolGenerator, WorkflowTool
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.controller.base import TaskState, TaskStatus
from mindor.core.foundation.streaming.base64 import encode_value_to_base64
from mindor.core.foundation.streaming.file import FileStreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.url import UrlStreamResource, DataUriStreamResource
from mindor.core.utils.transport.stdout_relay import StdoutRelay
from ..base import ControllerAdapterService, register_controller_adapter
from mcp.server.fastmcp.server import FastMCP
from mcp.server.stdio import stdio_server
from mcp.types import ContentBlock, TextContent, ImageContent, AudioContent, EmbeddedResource, BlobResourceContents
import asyncio, uvicorn, json

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

@register_controller_adapter(ControllerAdapterType.MCP_SERVER)
class McpServerControllerAdapterService(ControllerAdapterService):
    def __init__(
        self,
        config: McpServerControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool
    ):
        super().__init__(config, controller, daemon)

        self.http_server: Optional[uvicorn.Server] = None
        self.stdio_task: Optional[asyncio.Task] = None

        app_params = {}

        if self.config.transport == McpServerTransport.HTTP:
            app_params["streamable_http_path"] = self.config.base_path or "/"

        self.app: FastMCP = FastMCP(self.controller.config.name, **app_params)

        self._configure_workflow_tools()

    def _configure_workflow_tools(self) -> None:
        interruptable_workflow_ids = self._find_interruptable_workflow_ids()

        for workflow_id, workflow in self.controller.workflow_schemas.items():
            tool = WorkflowToolGenerator().generate(
                workflow_id,
                workflow,
                self._run_workflow_as_tool,
                interruptable=workflow_id in interruptable_workflow_ids,
            )
            self.app.add_tool(
                fn=tool.function,
                name=workflow.name or workflow_id,
                title=workflow.title,
                description=self._build_tool_description(tool),
                annotations=None
            )

        if interruptable_workflow_ids:
            tool = ResumeToolGenerator().generate("resume", self._resume_workflow_as_tool)
            self.app.add_tool(
                fn=tool.function,
                name="resume_workflow",
                title="Resume an interrupted workflow",
                description=self._build_tool_description(tool),
                annotations=None
            )

    def _build_tool_description(self, tool: WorkflowTool) -> str:
        lines = [ tool.description or "" ]

        if tool.parameters:
            lines.append("")
            lines.append("Args:")
            for param in tool.parameters:
                type_label = f"list[{param.type.value}]" if param.is_list else param.type.value
                description = param.get_annotation_value("description") or ""
                lines.append(f"    {param.name or 'input'} ({type_label}): {description}")

        if tool.returns:
            lines.append("")
            lines.append("Returns:")
            for variable in tool.returns:
                if isinstance(variable, WorkflowVariableGroupConfig):
                    lines.append(f"    {variable.name or 'output'} (list[object]): each item has:")
                    for inner in variable.variables:
                        type_label = f"list[{inner.type.value}]" if inner.is_list else inner.type.value
                        description = inner.get_annotation_value("description") or ""
                        lines.append(f"        {inner.name or 'output'} ({type_label}): {description}")
                else:
                    type_label = f"list[{variable.type.value}]" if variable.is_list else variable.type.value
                    description = variable.get_annotation_value("description") or ""
                    lines.append(f"    {variable.name or 'output'} ({type_label}): {description}")

        return "\n".join(lines)

    def _find_interruptable_workflow_ids(self) -> Set[str]:
        workflow_ids: Set[str] = set()

        for workflow in self.controller.workflows:
            for job in workflow.jobs:
                if job.interrupt and (job.interrupt.before or job.interrupt.after):
                    workflow_ids.add(workflow.id)
                    break

        return workflow_ids

    async def _run_workflow_as_tool(self, workflow_id: Optional[str], input: Any, context: Any = None) -> List[ContentBlock]:
        state = await self.controller.run_workflow(
            workflow_id,
            input,
            wait_for_completion=True
        )
        return await self._build_state_response(state)

    async def _resume_workflow_as_tool(self, task_id: str, job_id: str, run_id: Optional[str] = None, answer: str = "") -> List[ContentBlock]:
        parsed_answer = json.loads(answer) if answer else None
        try:
            await self.controller.resume_workflow(task_id, job_id, run_id, parsed_answer)
        except ValueError as e:
            return [ TextContent(type="text", text=json.dumps({"error": str(e)})) ]

        state = await self.controller.wait_for_terminal_state(task_id)
        return await self._build_state_response(state)

    async def _build_state_response(self, state: TaskState) -> List[ContentBlock]:
        if state.status == TaskStatus.INTERRUPTED:
            return [TextContent(type="text", text=json.dumps({
                "status": "interrupted",
                "task_id": state.task_id,
                "interrupt": {
                    "job_id": state.interrupt.job_id,
                    "run_id": state.interrupt.run_id,
                    "phase": state.interrupt.phase,
                    "message": state.interrupt.message,
                    "metadata": state.interrupt.metadata
                }
            }))]

        if state.status == TaskStatus.FAILED:
            return [ TextContent(type="text", text=json.dumps({"status": "failed", "error": state.error})) ]

        workflow = self.controller.workflow_schemas.get(state.workflow_id) if state.workflow_id else None
        if workflow:
            return await self._build_output_value(state, workflow)

        if state.output is None:
            return [ TextContent(type="text", text=json.dumps({"status": "completed"})) ]
        if isinstance(state.output, (dict, list)):
            return [ TextContent(type="text", text=json.dumps(state.output)) ]
        return [ TextContent(type="text", text=str(state.output)) ]

    async def _build_output_value(self, state: TaskState, workflow: WorkflowSchema) -> List[ContentBlock]:
        output: List[ContentBlock] = []

        if state.output:
            if len(workflow.output) == 1 and isinstance(workflow.output[0], WorkflowVariableConfig) and not workflow.output[0].name:
                variable = workflow.output[0]
                output.append(await self._convert_output_value(state.task_id, state.output, variable.name, variable.type, variable.subtype, variable.format))
            else:
                for variable in workflow.output:
                    if isinstance(variable, WorkflowVariableGroupConfig):
                        output.append(TextContent(type="text", text=json.dumps(state.output[variable.name], default=str)))
                    else:
                        output.append(await self._convert_output_value(state.task_id, state.output[variable.name], variable.name, variable.type, variable.subtype, variable.format))

        return output

    async def _convert_output_value(
        self,
        task_id: str,
        value: Any,
        name: Optional[str],
        type: WorkflowVariableType,
        subtype: Optional[str],
        format: Optional[WorkflowVariableFormat]
    ) -> ContentBlock:
        if type in (WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE):
            # Everything else must land as a base64 string (MCP media blocks demand it).
            data = await self._encode_media_value_to_base64(value, format)

            if type == WorkflowVariableType.IMAGE:
                return ImageContent(type="image", data=data, mimeType=f"image/{subtype or 'png'}")

            if type == WorkflowVariableType.AUDIO:
                return AudioContent(type="audio", data=data, mimeType=f"audio/{subtype or 'wav'}")

            if type == WorkflowVariableType.VIDEO:
                return EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri=f"resource://{task_id}/{name or 'output'}",
                        mimeType=f"video/{subtype or 'mp4'}",
                        blob=data
                    )
                )

            return EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    uri=f"resource://{task_id}/{name or 'output'}",
                    mimeType="application/octet-stream",
                    blob=data
                )
            )

        if type == WorkflowVariableType.NONE:
            return TextContent(type="text", text="")

        if isinstance(value, (StreamResource, StreamIterator)):
            return EmbeddedResource(
                type="resource",
                resource=BlobResourceContents(
                    uri=f"resource://{task_id}/{name or 'output'}",
                    mimeType="application/octet-stream",
                    blob=await encode_value_to_base64(value),
                ),
            )

        if isinstance(value, (dict, list)):
            return TextContent(type="text", text=json.dumps(value))

        return TextContent(type="text", text=str(value))

    async def _encode_media_value_to_base64(self, value: Any, format: Optional[WorkflowVariableFormat]) -> str:
        if format == WorkflowVariableFormat.BASE64 and isinstance(value, str):
            return value

        if format == WorkflowVariableFormat.PATH and isinstance(value, str):
            return await encode_value_to_base64(FileStreamResource(value))

        if format == WorkflowVariableFormat.URL and isinstance(value, str):
            return await encode_value_to_base64(UrlStreamResource(value))

        if format == WorkflowVariableFormat.DATA_URI and isinstance(value, str):
            return await encode_value_to_base64(DataUriStreamResource(value))

        return await encode_value_to_base64(value)

    async def _serve(self) -> None:
        if self.config.transport == McpServerTransport.STDIO:
            await self._serve_stdio()
        else:
            await self._serve_http()

    async def _serve_http(self) -> None:
        self.http_server = uvicorn.Server(uvicorn.Config(
            self.app.streamable_http_app(),
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        try:
            await self.http_server.serve()
        finally:
            self.http_server = None

    async def _serve_stdio(self) -> None:
        with StdoutRelay() as stdout_stream:
            async with stdio_server(stdout=stdout_stream) as (read_stream, write_stream):
                self.stdio_task = asyncio.create_task(self.app._mcp_server.run(
                    read_stream,
                    write_stream,
                    self.app._mcp_server.create_initialization_options(),
                ))
                try:
                    await self.stdio_task
                except asyncio.CancelledError:
                    pass
                finally:
                    self.stdio_task = None

    async def _shutdown(self) -> None:
        if self.http_server:
            self.http_server.should_exit = True

        if self.stdio_task:
            self.stdio_task.cancel()
