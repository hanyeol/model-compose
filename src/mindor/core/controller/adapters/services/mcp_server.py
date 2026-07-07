from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Optional, List, Any
from mindor.dsl.schema.controller import McpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.workflow import WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.tool import WorkflowToolGenerator, ResumeToolGenerator, WorkflowTool
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.controller.base import TaskState, TaskStatus
from ..base import ControllerAdapterService, register_controller_adapter
from mcp.server.fastmcp.server import FastMCP
from mcp.types import ContentBlock, TextContent, ImageContent, AudioContent, EmbeddedResource, BlobResourceContents
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

        self._configure_workflow_tools()

    def _configure_workflow_tools(self) -> None:
        for workflow_id, workflow in self.controller.workflow_schemas.items():
            tool = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow_as_tool)
            self.app.add_tool(
                fn=tool.function,
                name=workflow.name or workflow_id,
                title=workflow.title,
                description=self._build_tool_description(tool),
                annotations=None
            )

        self._configure_resume_tool()

    def _configure_resume_tool(self) -> None:
        tool = ResumeToolGenerator().generate("resume", self._resume_workflow_as_tool)
        self.app.add_tool(
            fn=tool.function,
            name="resume_workflow",
            title="Resume an interrupted workflow",
            description=self._build_tool_description(tool),
            annotations=None
        )

    async def _run_workflow_as_tool(self, workflow_id: Optional[str], input: Any, context: Any = None) -> List[ContentBlock]:
        state = await self.controller.run_workflow(
            workflow_id,
            input,
            wait_for_completion=True
        )
        return await self._build_state_response(state)

    async def _resume_workflow_as_tool(self, task_id: str, job_id: str, answer: str = "") -> List[ContentBlock]:
        parsed_answer = json.loads(answer) if answer else None
        try:
            await self.controller.resume_workflow(task_id, job_id, parsed_answer)
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
            if len(workflow.output) == 1 and not workflow.output[0].name:
                variable = workflow.output[0]
                output.append(self._convert_output_value(state.task_id, state.output, variable.name, variable.type, variable.subtype, variable.format))
            else:
                for variable in workflow.output:
                    output.append(self._convert_output_value(state.task_id, state.output[variable.name], variable.name, variable.type, variable.subtype, variable.format))

        return output

    def _convert_output_value(
        self,
        task_id: str,
        value: Any,
        name: Optional[str],
        type: WorkflowVariableType,
        subtype: Optional[str],
        format: Optional[WorkflowVariableFormat]
    ) -> ContentBlock:
        if type in (WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE):
            if format == WorkflowVariableFormat.BASE64:
                if type == WorkflowVariableType.IMAGE:
                    return ImageContent(type="image", data=value, mimeType=f"image/{subtype or 'png'}")

                if type == WorkflowVariableType.AUDIO:
                    return AudioContent(type="audio", data=value, mimeType=f"audio/{subtype or 'wav'}")

                return EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(
                        uri=f"resource://{task_id}/{name or 'output'}",
                        mimeType=f"video/{subtype or 'mp4'}" if type == WorkflowVariableType.VIDEO else "application/octet-stream",
                        blob=value
                    )
                )

            if format in (WorkflowVariableFormat.URL, WorkflowVariableFormat.DATA_URI):
                return TextContent(type="text", text=value)

            raise ValueError(f"`{type.value}` output requires `format` to be exposed over MCP (got {format}).")

        if type == WorkflowVariableType.NONE:
            return TextContent(type="text", text="")

        if isinstance(value, (dict, list)):
            return TextContent(type="text", text=json.dumps(value))

        return TextContent(type="text", text=str(value))

    def _build_tool_description(self, tool: WorkflowTool) -> str:
        lines = [ tool.description or "" ]

        if tool.parameters:
            lines.append("")
            lines.append("Args:")
            for param in tool.parameters:
                type_label = f"list[{param.type.value}]" if param.is_list else param.type.value
                description = param.get_annotation_value("description") or ""
                lines.append(f"    {param.name or 'input'} ({type_label}): {description}")

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
