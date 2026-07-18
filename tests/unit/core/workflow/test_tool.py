"""Unit tests for `core/workflow/tool.py`.

Scope:
- `WorkflowToolGenerator.generate` — produced function signature, delegation, and
  the fact that `WorkflowTool.parameters` is now the raw `WorkflowVariableConfig`
  list from `WorkflowSchema.input` (no lossy re-encoding).
- `ResumeToolGenerator.generate` — hardcoded resume parameters expressed as
  `WorkflowVariableConfig` objects.
"""

from __future__ import annotations

import inspect
from typing import Any, List, Optional

import pytest

from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.workflow.tool import (
    ResumeToolGenerator,
    WorkflowTool,
    WorkflowToolGenerator,
)
from mindor.dsl.schema.workflow import (
    WorkflowVariableAnnotationConfig,
    WorkflowVariableConfig,
    WorkflowVariableFormat,
    WorkflowVariableType,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _var(
    name: Optional[str],
    type: WorkflowVariableType,
    *,
    is_list: bool = False,
    subtype: Optional[str] = None,
    format: Optional[WorkflowVariableFormat] = None,
    options: Optional[List[str]] = None,
    required: bool = False,
    default: Any = None,
    description: Optional[str] = None,
) -> WorkflowVariableConfig:
    annotations = (
        [WorkflowVariableAnnotationConfig(name="description", value=description)]
        if description
        else []
    )
    return WorkflowVariableConfig(
        name=name,
        type=type,
        is_list=is_list,
        subtype=subtype,
        format=format,
        options=options,
        required=required,
        default=default,
        annotations=annotations,
    )


def _schema(
    input_vars: List[WorkflowVariableConfig],
    *,
    workflow_id: str = "search-docs",
    name: Optional[str] = "search_docs",
    title: Optional[str] = "Search Docs",
    description: Optional[str] = "Search the internal documentation store.",
) -> WorkflowSchema:
    return WorkflowSchema(
        workflow_id=workflow_id,
        name=name,
        title=title,
        description=description,
        input=input_vars,
        output=[],
        default=False,
    )


class TestWorkflowToolGenerator:
    def test_parameters_are_workflowvariableconfig_untouched(self) -> None:
        query = _var("query", WorkflowVariableType.STRING, required=True, description="q")
        limit = _var("limit", WorkflowVariableType.INTEGER, default=10)

        schema = _schema([query, limit])
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, runner=_noop_runner)

        # New contract: parameters is the raw list from workflow.input (identity preserved).
        assert isinstance(tool, WorkflowTool)
        assert tool.parameters is schema.input
        assert tool.parameters == [query, limit]

    def test_description_prefers_workflow_description_falls_back_to_title(self) -> None:
        schema_with_desc = _schema([], description="D", title="T")
        schema_title_only = _schema([], description=None, title="T")
        schema_neither = _schema([], description=None, title=None)

        assert (
            WorkflowToolGenerator()
            .generate(schema_with_desc.workflow_id, schema_with_desc, _noop_runner)
            .description
            == "D"
        )
        assert (
            WorkflowToolGenerator()
            .generate(schema_title_only.workflow_id, schema_title_only, _noop_runner)
            .description
            == "T"
        )
        assert (
            WorkflowToolGenerator()
            .generate(schema_neither.workflow_id, schema_neither, _noop_runner)
            .description
            is None
        )

    def test_description_unchanged_when_not_interruptable(self) -> None:
        schema = _schema([], description="Do the thing.")
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, _noop_runner)
        assert tool.description == "Do the thing."

    def test_description_appends_interrupt_hint_when_interruptable(self) -> None:
        schema = _schema([], description="Do the thing.")
        tool = WorkflowToolGenerator().generate(
            schema.workflow_id, schema, _noop_runner, interruptable=True,
        )
        assert tool.description.startswith("Do the thing.\n\n")
        assert "resume_workflow" in tool.description
        assert "Human-in-the-Loop" in tool.description

    def test_interrupt_hint_is_standalone_when_workflow_has_no_description(self) -> None:
        schema = _schema([], description=None, title=None)
        tool = WorkflowToolGenerator().generate(
            schema.workflow_id, schema, _noop_runner, interruptable=True,
        )
        assert tool.description is not None
        assert "resume_workflow" in tool.description
        assert not tool.description.startswith("\n")

    def test_generated_function_has_named_parameters_from_input(self) -> None:
        schema = _schema(
            [
                _var("query", WorkflowVariableType.STRING),
                _var("limit", WorkflowVariableType.INTEGER),
            ]
        )
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, _noop_runner)

        sig = inspect.signature(tool.function)
        # Each workflow input becomes a keyword argument, plus the trailing `context`.
        assert list(sig.parameters) == ["query", "limit", "context"]
        assert sig.parameters["query"].default is None
        assert sig.parameters["context"].default is None

    def test_generated_function_uses_input_fallback_when_variable_unnamed(self) -> None:
        # Anonymous input variables collapse to a single positional keyword "input".
        schema = _schema([_var(None, WorkflowVariableType.STRING)])
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, _noop_runner)

        sig = inspect.signature(tool.function)
        assert list(sig.parameters) == ["input", "context"]

    def test_generated_function_handles_empty_input(self) -> None:
        # A workflow with no inputs still needs a callable; the generator injects `_`.
        schema = _schema([])
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, _noop_runner)

        sig = inspect.signature(tool.function)
        assert list(sig.parameters) == ["_", "context"]

    @pytest.mark.anyio
    async def test_generated_function_delegates_to_runner_with_named_input_dict(self) -> None:
        schema = _schema(
            [
                _var("query", WorkflowVariableType.STRING),
                _var("limit", WorkflowVariableType.INTEGER),
            ]
        )

        captured: dict = {}

        async def runner(workflow_id: str, input: Any, context: Any = None) -> Any:
            captured["workflow_id"] = workflow_id
            captured["input"] = input
            captured["context"] = context
            return {"echo": input}

        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, runner)
        result = await tool.function(query="hello", limit=5, context={"caller": "test"})

        assert captured["workflow_id"] == "search-docs"
        assert captured["input"] == {"query": "hello", "limit": 5}
        assert captured["context"] == {"caller": "test"}
        assert result == {"echo": {"query": "hello", "limit": 5}}

    @pytest.mark.anyio
    async def test_generated_function_forwards_defaults_when_argument_omitted(self) -> None:
        schema = _schema(
            [
                _var("query", WorkflowVariableType.STRING),
                _var("limit", WorkflowVariableType.INTEGER),
            ]
        )
        captured: dict = {}

        async def runner(workflow_id: str, input: Any, context: Any = None) -> Any:
            captured["input"] = input
            return None

        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, runner)
        await tool.function(query="q")  # limit omitted → default None per generated signature.

        assert captured["input"] == {"query": "q", "limit": None}

    def test_workflow_id_with_special_characters_is_sanitized_for_function_name(self) -> None:
        # Function names cannot contain `-` or `.`; the generator must sanitize them.
        schema = _schema([_var("x", WorkflowVariableType.STRING)], workflow_id="my-cool.workflow!")
        tool = WorkflowToolGenerator().generate(schema.workflow_id, schema, _noop_runner)

        # The runtime callable is still valid; its Python name reflects sanitization.
        assert tool.function.__name__ == "_run_workflow_my_cool_workflow_"


class TestResumeToolGenerator:
    def test_produces_workflowvariableconfig_parameters(self) -> None:
        tool = ResumeToolGenerator().generate("resume", runner=_noop_resume_runner)

        assert all(isinstance(p, WorkflowVariableConfig) for p in tool.parameters)
        names = [p.name for p in tool.parameters]
        assert names == ["task_id", "job_id", "run_id", "answer"]

    def test_parameter_types_and_required_flags_match_original_contract(self) -> None:
        tool = ResumeToolGenerator().generate("resume", _noop_resume_runner)
        params = {p.name: p for p in tool.parameters}

        assert params["task_id"].type == WorkflowVariableType.STRING
        assert params["task_id"].required is True
        assert params["task_id"].default is None

        assert params["job_id"].type == WorkflowVariableType.STRING
        assert params["job_id"].required is True
        assert params["job_id"].default is None

        assert params["answer"].type == WorkflowVariableType.STRING
        assert params["answer"].required is False
        # `answer` intentionally defaults to empty string to remain optional at call site.
        assert params["answer"].default == ""

    def test_description_is_stored_as_annotation(self) -> None:
        # Descriptions must round-trip through the annotations list, not a top-level field.
        tool = ResumeToolGenerator().generate("resume", _noop_resume_runner)
        params = {p.name: p for p in tool.parameters}

        assert (
            params["task_id"].get_annotation_value("description")
            == "The task ID of the interrupted workflow"
        )
        assert (
            params["job_id"].get_annotation_value("description")
            == "The job ID where the interrupt occurred"
        )
        assert (
            params["answer"].get_annotation_value("description")
            == "Optional JSON string with answer to resume with"
        )

    def test_tool_description_present(self) -> None:
        tool = ResumeToolGenerator().generate("resume", _noop_resume_runner)
        assert tool.description is not None
        assert "Human-in-the-Loop" in tool.description

    @pytest.mark.anyio
    async def test_generated_function_forwards_arguments_to_runner(self) -> None:
        captured: dict = {}

        async def runner(task_id: str, job_id: str, run_id: Any, answer: Any) -> Any:
            captured.update(task_id=task_id, job_id=job_id, run_id=run_id, answer=answer)
            return "resumed"

        tool = ResumeToolGenerator().generate("resume", runner)
        result = await tool.function(task_id="t1", job_id="j1", run_id="r1", answer='{"ok":true}')

        assert result == "resumed"
        assert captured == {"task_id": "t1", "job_id": "j1", "run_id": "r1", "answer": '{"ok":true}'}


async def _noop_runner(workflow_id: str, input: Any, context: Any = None) -> Any:
    return None


async def _noop_resume_runner(task_id: str, job_id: str, run_id: Any, answer: Any) -> Any:
    return None
