from typing import Optional, Dict, List, Tuple, Callable, Awaitable, Any
from dataclasses import dataclass
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableType, WorkflowVariableFormat, WorkflowVariableAnnotationConfig
from mindor.dsl.schema.common.model.tool import ModelTool, ModelToolParameters, ModelToolProperty
from mindor.core.workflow.schema import WorkflowSchema
import re

_INVALID_FUNCTION_CHARS_REGEX = re.compile(r"[^a-zA-Z0-9_]")

_MODEL_TOOL_TYPE_MAP: Dict[WorkflowVariableType, str] = {
    WorkflowVariableType.STRING:   "string",
    WorkflowVariableType.TEXT:     "string",
    WorkflowVariableType.MARKDOWN: "string",
    WorkflowVariableType.BASE64:   "string",
    WorkflowVariableType.IMAGE:    "string",
    WorkflowVariableType.AUDIO:    "string",
    WorkflowVariableType.VIDEO:    "string",
    WorkflowVariableType.FILE:     "string",
    WorkflowVariableType.SELECT:   "string",
    WorkflowVariableType.INTEGER:  "integer",
    WorkflowVariableType.NUMBER:   "number",
    WorkflowVariableType.BOOLEAN:  "boolean",
    WorkflowVariableType.LIST:     "array",
    WorkflowVariableType.OBJECT:   "object",
    WorkflowVariableType.JSON:     "object",
}

@dataclass
class WorkflowTool:
    function: Callable[[Any], Awaitable[Any]]
    description: Optional[str]
    parameters: List[WorkflowVariableConfig]

    def as_model_tool(self, name: str) -> ModelTool:
        properties: Dict[str, ModelToolProperty] = {}
        required: List[str] = []

        for param in self.parameters:
            param_name = param.name or "input"
            properties[param_name] = self._build_parameter_property(param)
            if param.required:
                required.append(param_name)

        return ModelTool(
            name=name,
            description=self.description,
            parameters=ModelToolParameters(properties=properties, required=required),
        )

    def _build_parameter_property(self, param: WorkflowVariableConfig) -> ModelToolProperty:
        scalar = self._build_scalar_property(param)

        if param.is_list:
            property = ModelToolProperty(type="array", items=scalar)
        else:
            property = scalar

        description = param.get_annotation_value("description")

        if description:
            property.description = description

        if param.default is not None:
            property.default = param.default

        return property

    def _build_scalar_property(self, param: WorkflowVariableConfig) -> ModelToolProperty:
        json_type = _MODEL_TOOL_TYPE_MAP.get(param.type, "string")
        property = ModelToolProperty(type=json_type)

        if param.type == WorkflowVariableType.SELECT and param.options:
            property.enum = param.options

        return property

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
            parameters=workflow.input
        )

    async def _build_input_value(self, arguments: List[Any], workflow: WorkflowSchema) -> Any:
        input: Dict[str, Any] = {}

        for value, variable in zip(arguments, workflow.input):
            input[variable.name or "input"] = value

        return input

class ResumeToolGenerator():
    def generate(
        self,
        workflow_id: str,
        runner: Callable[[str, str, Optional[str], Any], Awaitable[Any]]
    ) -> WorkflowTool:
        async def _resume_workflow(task_id, job_id, run_id=None, answer=None) -> Any:
            return await runner(task_id, job_id, run_id, answer)

        safe_workflow_id = re.sub(_INVALID_FUNCTION_CHARS_REGEX, "_", workflow_id)
        code = (
            f"async def _resume_workflow_{safe_workflow_id}(task_id=None, job_id=None, run_id=None, answer=''):\n"
            f"    return await _resume_workflow(task_id, job_id, run_id, answer)"
        )
        context = { "_resume_workflow": _resume_workflow }
        exec(compile(code, f"<string>", "exec"), context)

        return WorkflowTool(
            function=context[f"_resume_workflow_{safe_workflow_id}"],
            description="Resume a workflow that was paused at a Human-in-the-Loop interrupt point.",
            parameters=[
                self._build_parameter("task_id", "The task ID of the interrupted workflow", required=True),
                self._build_parameter("job_id",  "The job ID where the interrupt occurred",  required=True),
                self._build_parameter("run_id",  "The run ID where the interrupt occurred", default=None, required=False),
                self._build_parameter("answer",  "Optional JSON string with answer to resume with", default="", required=False),
            ]
        )

    def _build_parameter(self, name: str, description: str, default: Any = None, required: bool = False) -> WorkflowVariableConfig:
        return WorkflowVariableConfig(
            name=name,
            type=WorkflowVariableType.STRING,
            default=default,
            required=required,
            annotations=[ WorkflowVariableAnnotationConfig(name="description", value=description) ]
        )
