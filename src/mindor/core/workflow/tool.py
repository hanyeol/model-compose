from typing import Optional, Dict, List, Tuple, Callable, Awaitable, Any
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.schema import WorkflowSchema
import re

_invalid_function_chars_regex = re.compile(r"[^a-zA-Z0-9_]")

class WorkflowToolGenerator():
    def generate(self, workflow_id: str, workflow: WorkflowSchema, runner: Callable[[Optional[str], Any], Awaitable[Any]]) -> Tuple[Callable[[Any], Awaitable[Any]], str]:
        async def _run_workflow(input: Any, workflow_id=workflow_id) -> Any:
            return await runner(workflow_id, input)

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
            input[variable.name or "input"] = await self._convert_input_value(value, variable.type, variable.subtype, variable.format, variable.default)

        return input

    async def _convert_input_value(self, value: Any, type: WorkflowVariableType, subtype: Optional[str], format: Optional[WorkflowVariableFormat], default: Optional[Any]) -> Any:
        if type in [ WorkflowVariableType.IMAGE, WorkflowVariableType.AUDIO, WorkflowVariableType.VIDEO, WorkflowVariableType.FILE ]:
            if format and format != "path":
                pass

        return value if value != "" else None

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
        if variable.type == WorkflowVariableType.OBJECTS:
            return "list[dict]"

        if variable.type == WorkflowVariableType.NUMBER:
            return "float"

        if variable.type == WorkflowVariableType.INTEGER:
            return "int"

        return "str"
