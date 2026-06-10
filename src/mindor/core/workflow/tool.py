from typing import Optional, Dict, List, Tuple, Callable, Awaitable, Any
from dataclasses import dataclass
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableType, WorkflowVariableFormat
from mindor.core.workflow.schema import WorkflowSchema
import re

_INVALID_FUNCTION_CHARS_REGEX = re.compile(r"[^a-zA-Z0-9_]")

@dataclass
class WorkflowToolParameter:
    name: str
    type: str
    description: Optional[str]
    default: Optional[Any]
    required: bool

@dataclass
class WorkflowTool:
    function: Callable[[Any], Awaitable[Any]]
    description: Optional[str]
    parameters: List[WorkflowToolParameter]

class WorkflowToolGenerator():
    def generate(
        self,
        workflow_id: str,
        workflow: WorkflowSchema,
        runner: Callable[[str, Any, Any], Awaitable[Any]]
    ) -> WorkflowTool:
        async def _run_workflow(workflow_id, input: Any, context=None) -> Any:
            return await runner(workflow_id, input, context)

        async def _build_input_value(arguments, workflow=workflow) -> Any:
            return await self._build_input_value(arguments, workflow)

        safe_workflow_id = re.sub(_INVALID_FUNCTION_CHARS_REGEX, "_", workflow_id)
        arguments = ", ".join([ variable.name or "input" for variable in workflow.input ])
        declarations = ", ".join([ f"{variable.name or 'input'}=None" for variable in workflow.input ])
        code = (
            f"async def _run_workflow_{safe_workflow_id}({declarations or '_=None'}, context=None):\n"
            f"    return await _run_workflow(\n"
            f"        '{workflow_id}',\n"
            f"        await _build_input_value([{arguments}]),\n"
            f"        context=context\n"
            f"    )"
        )
        context = { "_run_workflow": _run_workflow, "_build_input_value": _build_input_value }
        exec(compile(code, f"<string>", "exec"), context)

        return WorkflowTool(
            function=context[f"_run_workflow_{safe_workflow_id}"],
            description=workflow.description or workflow.title,
            parameters=self._generate_parameters(workflow)
        )

    async def _build_input_value(self, arguments: List[Any], workflow: WorkflowSchema) -> Any:
        input: Dict[str, Any] = {}

        for value, variable in zip(arguments, workflow.input):
            input[variable.name or "input"] = value

        return input

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
        if variable.type == WorkflowVariableType.LIST:
            return "list[list]" if variable.is_list else "list"

        if variable.type == WorkflowVariableType.OBJECT:
            return "list[dict]" if variable.is_list else "dict"

        if variable.type == WorkflowVariableType.NUMBER:
            return "list[float]" if variable.is_list else "float"

        if variable.type == WorkflowVariableType.INTEGER:
            return "list[int]" if variable.is_list else "int"

        return "list[str]" if variable.is_list else "str"

class ResumeToolGenerator():
    def generate(
        self,
        workflow_id: str,
        runner: Callable[[str, str, Any], Awaitable[Any]]
    ) -> WorkflowTool:
        async def _resume_workflow(task_id, job_id, answer=None) -> Any:
            return await runner(task_id, job_id, answer)

        safe_workflow_id = re.sub(_INVALID_FUNCTION_CHARS_REGEX, "_", workflow_id)
        code = (
            f"async def _resume_workflow_{safe_workflow_id}(task_id=None, job_id=None, answer=''):\n"
            f"    return await _resume_workflow(task_id, job_id, answer)"
        )
        context = { "_resume_workflow": _resume_workflow }
        exec(compile(code, f"<string>", "exec"), context)

        return WorkflowTool(
            function=context[f"_resume_workflow_{safe_workflow_id}"],
            description="Resume a workflow that was paused at a Human-in-the-Loop interrupt point.",
            parameters=[
                WorkflowToolParameter(name="task_id", type="str", description="The task ID of the interrupted workflow", default=None, required=True),
                WorkflowToolParameter(name="job_id",  type="str", description="The job ID where the interrupt occurred",  default=None, required=True),
                WorkflowToolParameter(name="answer",  type="str", description="Optional JSON string with answer to resume with", default="", required=False),
            ]
        )
