from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Awaitable, Any
from mindor.dsl.schema.controller import McpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig
from mindor.core.workflow.schema import WorkflowSchema, create_workflow_schema
from mindor.core.utils.streaming import StreamResource, Base64StreamResource
from mindor.core.utils.streaming import save_stream_to_temporary_file
from mindor.core.utils.http_client import create_stream_with_url
from .base import ControllerEngine, ControllerType, ControllerEngineMap, TaskState
from mcp.server.fastmcp.server import FastMCP
from mcp.types import TextContent, ImageContent, AudioContent
import uvicorn, re, json

_invalid_function_chars_regex = re.compile(r"[^a-zA-Z0-9_]")

class WorkflowToolGenerator():
    def generate(self, workflow_id: str, workflow: WorkflowSchema, runner: Callable[[Optional[str], Any], Awaitable[Any]]) -> Tuple[Callable[[Any], Awaitable[Any]], str]:
        async def _run_workflow(input: Any, workflow_id=workflow_id, workflow=workflow) -> Any:
            return await self._build_output_value(await runner(workflow_id, input), workflow)

        async def _build_input_value(arguments, workflow=workflow) -> Any:
            return await self._build_input_value(arguments, workflow)

        safe_workflow_id = re.sub(_invalid_function_chars_regex, "_", workflow_id)
        arguments = ",".join([ variable.name or "input" for variable in workflow.input ])
        code = f"async def _run_workflow_{safe_workflow_id}({arguments}): return await _run_workflow(await _build_input_value([{arguments}]))"
        context = { "_run_workflow": _run_workflow, "_build_input_value": _build_input_value }
        exec(compile(code, f"<string>", "exec"), context)

        return (context[f"_run_workflow_{safe_workflow_id}"], self._generate_description(workflow))

    async def _build_input_value(self, arguments: List[Any], workflow: WorkflowSchema) -> Any:
        input: Dict[str, Any] = {}

        for value, variable in zip(arguments, workflow.input):
            type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
            input[variable.name or "input"] = await self._convert_input_value(value, type, subtype, format, variable.default)

        return input

    async def _convert_input_value(self, value: Any, type: str, subtype: Optional[str], format: Optional[str], default: Optional[Any]) -> Any:
        if type in [ "image", "audio", "video", "file" ]:
            if format and format != "path":
                pass

        return value if value != "" else None

    async def _build_output_value(self, state: TaskState, workflow: WorkflowSchema) -> List[Union[TextContent, ImageContent, AudioContent]]:
        output: List[Union[TextContent, ImageContent]] = []

        if state.output:
            if len(workflow.output) == 1 and not workflow.output[0].name:
                variable = workflow.output[0]
                type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
                output.append(await self._convert_output_value(state.output, type, subtype, format))
            else:
                for variable in workflow.output:
                    type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None
                    output.append(await self._convert_output_value(state.output[variable.name], type, subtype, format))

        return output

    async def _convert_output_value(self, value: Any, type: str, subtype: Optional[str], format: Optional[str]) -> Union[TextContent, ImageContent, AudioContent]:
        if type in [ "image", "audio", "video", "file" ]:
            if format == "base64" and len(value) < 1024 * 1024: # at most 1MB
                if type == "image":
                    return ImageContent(type="image", data=value, mimeType=f"{type}/{subtype}")
                if type == "audio":
                    return AudioContent(type="audio", data=value, mimeType=f"{type}/{subtype}")
            if not format or format not in [ "path", "url" ]:
                value = await self._save_value_to_temporary_file(value, subtype, format)
            return TextContent(type="text", text=value)

        if isinstance(value, (dict, list)):
            return TextContent(type="text", text=json.dumps(value))

        return TextContent(type="text", text=str(value))

    async def _save_value_to_temporary_file(self, value: Any, subtype: Optional[str], format: Optional[str]) -> Optional[str]:
        if format == "base64" and isinstance(value, str):
            return await save_stream_to_temporary_file(Base64StreamResource(value), subtype)

        if format == "url" and isinstance(value, str):
            return await save_stream_to_temporary_file(await create_stream_with_url(value), subtype)

        if isinstance(value, StreamResource):
            return await save_stream_to_temporary_file(value, subtype)

        return None

    def _generate_description(self, workflow: WorkflowSchema) -> str:
        lines = []

        lines.append(workflow.description or workflow.title or "")
        lines.append("")
        lines.append("Args:")

        for variable in workflow.input:
            name, type = variable.name or "input", self._get_docstring_type(variable)
            description = variable.get_annotation_value("description") or ""
            lines.append(f"    {name} ({type}): {description}")

        lines.append("")
        lines.append("Returns:")

        if len(workflow.output) == 1 and not workflow.output[0].name:
            variable = workflow.output[0]
            name, type = variable.name or "output", self._get_docstring_type(variable)
            description = variable.get_annotation_value("description") or ""
            lines.append(f"    {name} ({type}): {description}")
        else:
            for variable in workflow.output:
                name, type = variable.name or "output", self._get_docstring_type(variable)
                description = variable.get_annotation_value("description") or ""
                lines.append(f"    {name} ({type}): {description}")

        return "\n".join(lines)

    def _get_docstring_type(self, variable: WorkflowVariableConfig) -> str:
        type, subtype, format = variable.type.value, variable.subtype, variable.format.value if variable.format else None

        if type == "object[]":
            return "list[dict]"

        if type == "number":
            return "float"

        if type == "integer":
            return "int"

        return "str"

class McpServerController(ControllerEngine):
    def __init__(
        self,
        config: McpServerControllerConfig,
        components: Dict[str, ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: Dict[str, WorkflowConfig],
        daemon: bool
    ):
        super().__init__(config, components, listeners, gateways, workflows, daemon)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastMCP = FastMCP(self.config.name, **{
            "streamable_http_path": self.config.base_path
        })

        self._configure_tools()

    def _configure_tools(self) -> None:
        schema = create_workflow_schema(self.workflows, self.components)

        for workflow_id, workflow in schema.items():
            fn, description = WorkflowToolGenerator().generate(workflow_id, workflow, self._run_workflow_as_tool)
            self.app.add_tool(
                fn=fn,
                name=workflow.name or workflow_id,
                title=workflow.title,
                description=description,
                annotations=None
            )
    
    async def _run_workflow_as_tool(self, workflow_id: Optional[str], input: Any) -> TaskState:
        return await self.run_workflow(workflow_id, input, wait_for_completion=True)

    async def _serve(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app.streamable_http_app(),
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        await self.server.serve()
        self.server = None

    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True

ControllerEngineMap[ControllerType.MCP_SERVER] = McpServerController
