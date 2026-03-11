from typing import Optional, Dict, List, Tuple, Callable, Awaitable, Any
from dataclasses import dataclass
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.schema import WorkflowSchema
import re

_invalid_function_chars_regex = re.compile(r"[^a-zA-Z0-9_]")

@dataclass
class WorkflowToolParameter:
    name: str
    type: str
    description: Optional[str]
    default: Optional[Any]
    required: bool

@dataclass
class WorkflowTool:
    fn: Callable[[Any], Awaitable[Any]]
    description: Optional[str]
    parameters: List[WorkflowToolParameter]

class WorkflowToolGenerator():
    def generate(self, workflow_id: str, workflow: WorkflowSchema, runner: Callable[[str, Any, Any], Awaitable[Any]]) -> WorkflowTool:
        async def _run_workflow(workflow_id, input: Any, context=None) -> Any:
            return await runner(workflow_id, input, context)

        async def _build_input_value(arguments, workflow=workflow) -> Any:
            return await self._build_input_value(arguments, workflow)

        safe_workflow_id = re.sub(_invalid_function_chars_regex, "_", workflow_id)
        arguments = ",".join([ variable.name or "input" for variable in workflow.input ])
        code = f"async def _run_workflow_{safe_workflow_id}({arguments}, context=None): return await _run_workflow('{workflow_id}', await _build_input_value([{arguments}]), context=context)"
        context = { "_run_workflow": _run_workflow, "_build_input_value": _build_input_value }
        exec(compile(code, f"<string>", "exec"), context)

        return WorkflowTool(
            fn=context[f"_run_workflow_{safe_workflow_id}"],
            description=workflow.description or workflow.title,
            parameters=self._generate_parameters(workflow)
        )

    async def _build_input_value(self, arguments: List[Any], workflow: WorkflowSchema) -> Any:
        input: Dict[str, Any] = {}

        for value, variable in zip(arguments, workflow.input):
            input[variable.name or "input"] = await self._convert_input_value(value, variable.type, variable.subtype, variable.format, variable.default)

        return input

    async def _convert_input_value(self, value: Any, type: WorkflowVariableType, subtype: Optional[str], format: Optional[WorkflowVariableFormat], default: Optional[Any]) -> Any:
        if type in [ WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ]:
            if format and format != "path":
                pass

        return value if value != "" else None

    def _generate_parameters(self, workflow: WorkflowSchema) -> List[WorkflowToolParameter]:
        return [
            WorkflowToolParameter(
                name=variable.name or "input",
                type=self._get_type(variable),
                description=variable.get_annotation_value("description"),
                default=variable.default,
                required=variable.required
            )
            for variable in workflow.input
        ]

    def _get_type(self, variable: WorkflowVariableConfig) -> str:
        if variable.type == WorkflowVariableType.OBJECTS:
            return "list[dict]"

        if variable.type == WorkflowVariableType.NUMBER:
            return "float"

        if variable.type == WorkflowVariableType.INTEGER:
            return "int"

        return "str"
