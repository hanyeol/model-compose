from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Any
from mindor.dsl.schema.controller import McpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.workflow import WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.tool import WorkflowToolGenerator, WorkflowTool
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.utils.streaming import StreamResource, Base64StreamResource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.utils.http_client import create_stream_with_url
from mindor.core.controller.base import TaskState, TaskStatus
from ..base import ControllerAdapterService, register_controller_adapter
from mcp.server.fastmcp.server import FastMCP
from mcp.types import ContentBlock, TextContent, ImageContent, AudioContent
import uvicorn, json

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

        self.server: Optional[uvicorn.Server] = None
        self.app: FastMCP = FastMCP(self.controller.config.name, **{
            "streamable_http_path": self.config.base_path or "/"
        })

        self._configure_tools()

    def _configure_tools(self) -> None:
        for workflow_id, workflow in self.controller.workflow_schemas.items():
            tool = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow_as_tool)
            self.app.add_tool(
                fn=tool.fn,
                name=workflow.name or workflow_id,
                title=workflow.title,
                description=self._build_tool_description(tool),
                annotations=None
            )

        self._configure_resume_tool()

    def _configure_resume_tool(self) -> None:
        async def resume_workflow(task_id: str, job_id: str, answer: str = "") -> List[ContentBlock]:
            parsed_answer = json.loads(answer) if answer else None
            try:
                await self.controller.resume_workflow(task_id, job_id, parsed_answer)
            except ValueError as e:
                return [ TextContent(type="text", text=json.dumps({"error": str(e)})) ]

            state = await self.controller.wait_for_terminal_state(task_id)
            return await self._build_state_response(state)

        self.app.add_tool(
            fn=resume_workflow,
            name="resume_workflow",
            title="Resume an interrupted workflow",
            description="Resume a workflow that was paused at a Human-in-the-Loop interrupt point.\n\nArgs:\n    task_id (str): The task ID of the interrupted workflow\n    job_id (str): The job ID where the interrupt occurred\n    answer (str): Optional JSON string with answer to resume with",
            annotations=None
        )

    async def _run_workflow_as_tool(self, workflow_id: Optional[str], input: Any) -> List[ContentBlock]:
        state = await self.controller.run_workflow(workflow_id, input, wait_for_completion=True)
        return await self._build_state_response(state)

    async def _build_state_response(self, state: TaskState) -> List[ContentBlock]:
        if state.status == TaskStatus.INTERRUPTED:
            return [TextContent(type="text", text=json.dumps({
                "status": "interrupted",
                "task_id": state.task_id,
                "interrupt": {
                    "job_id": state.interrupt.job_id,
                    "phase": state.interrupt.phase,
                    "message": state.interrupt.message,
                    "metadata": state.interrupt.metadata
                }
            }))]

        if state.status == TaskStatus.FAILED:
            return [TextContent(type="text", text=json.dumps({"status": "failed", "error": state.error}))]

        workflow = self.controller.workflow_schemas.get(state.workflow_id) if state.workflow_id else None
        if workflow:
            return await self._build_output_value(state, workflow)

        if state.output is None:
            return [TextContent(type="text", text=json.dumps({"status": "completed"}))]
        if isinstance(state.output, (dict, list)):
            return [TextContent(type="text", text=json.dumps(state.output))]
        return [TextContent(type="text", text=str(state.output))]

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
