"""Unit tests for `McpServerControllerAdapterService._build_tool_description`.

This is the free-text `description` string FastMCP passes to the LLM alongside
the machine-readable `inputSchema`. It follows a Google-style docstring layout:

    <tool description>

    Args:
        <name> (<type>): <description>

    Returns:
        <name> (<type>): <description>

List parameters are rendered as `list[<type>]` — the Python/PEP 585 form, which
is the most common convention among FastMCP-based servers.
"""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

from mindor.core.controller.adapters.services.mcp_server import (
    McpServerControllerAdapterService,
)
from mindor.core.workflow.tool import WorkflowTool
from mindor.dsl.schema.workflow import (
    WorkflowVariableAnnotationConfig,
    WorkflowVariableConfig,
    WorkflowVariableGroupConfig,
    WorkflowVariableType,
)


@pytest.fixture
def adapter() -> McpServerControllerAdapterService:
    # Skip __init__ (it needs a full controller); we only exercise the renderer.
    return McpServerControllerAdapterService.__new__(McpServerControllerAdapterService)


def _var(
    name: Optional[str],
    type: WorkflowVariableType,
    *,
    is_list: bool = False,
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
        annotations=annotations,
    )


def _tool(
    params: List[WorkflowVariableConfig],
    description: Optional[str] = None,
    returns: Optional[List[Any]] = None,
) -> WorkflowTool:
    return WorkflowTool(
        function=_noop,
        description=description,
        parameters=params,
        returns=returns or [],
    )


async def _noop(*args: Any, **kwargs: Any) -> Any:
    return None


class TestListNotation:
    def test_scalar_uses_bare_type_name(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool([_var("q", WorkflowVariableType.STRING, description="query")])
        text = adapter._build_tool_description(tool)

        assert "q (string): query" in text
        assert "list[" not in text  # scalar must not be wrapped

    def test_is_list_wraps_type_in_list_bracket(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        # Python/PEP 585 style — the convention for FastMCP-based tools.
        tool = _tool([_var("tags", WorkflowVariableType.STRING, is_list=True, description="tag filter")])
        text = adapter._build_tool_description(tool)

        assert "tags (list[string]): tag filter" in text

    def test_list_wrapping_uses_workflow_type_value_not_python_alias(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        # `integer` (the DSL enum value), not `int`.
        tool = _tool([_var("counts", WorkflowVariableType.INTEGER, is_list=True)])
        text = adapter._build_tool_description(tool)

        assert "counts (list[integer])" in text

    def test_bare_list_type_without_is_list_stays_list(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        # `type=list, is_list=False` means the value itself is a list of unknown
        # items; the label is just `list`, not `list[list]`.
        tool = _tool([_var("bag", WorkflowVariableType.LIST)])
        text = adapter._build_tool_description(tool)

        assert "bag (list):" in text

    def test_list_of_list_reflects_both_layers(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        # `type=list, is_list=True` is a list-of-lists in the DSL model.
        tool = _tool([_var("matrix", WorkflowVariableType.LIST, is_list=True)])
        text = adapter._build_tool_description(tool)

        assert "matrix (list[list])" in text


class TestLayout:
    def test_omits_args_block_when_no_parameters(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        text = adapter._build_tool_description(_tool([], description="No inputs."))

        assert text == "No inputs."
        assert "Args:" not in text

    def test_includes_args_block_when_parameters_present(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [_var("q", WorkflowVariableType.STRING, description="query")],
            description="Search.",
        )
        text = adapter._build_tool_description(tool)

        assert text.splitlines() == [
            "Search.",
            "",
            "Args:",
            "    q (string): query",
        ]

    def test_missing_tool_description_produces_empty_first_line(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        # Google-style docstrings still work when the summary is empty; the
        # renderer emits a blank line rather than dropping the Args block.
        tool = _tool([_var("q", WorkflowVariableType.STRING)])
        text = adapter._build_tool_description(tool)

        lines = text.splitlines()
        assert lines[0] == ""
        assert "Args:" in lines

    def test_missing_parameter_description_leaves_empty_after_colon(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool([_var("q", WorkflowVariableType.STRING)])
        text = adapter._build_tool_description(tool)

        assert "    q (string): " in text

    def test_anonymous_parameter_falls_back_to_input(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool([_var(None, WorkflowVariableType.STRING, description="the input")])
        text = adapter._build_tool_description(tool)

        assert "    input (string): the input" in text


class TestMixedParameters:
    def test_scalars_and_lists_coexist_with_consistent_notation(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [
                _var("query", WorkflowVariableType.STRING, description="q"),
                _var("tags", WorkflowVariableType.STRING, is_list=True, description="filters"),
                _var("limit", WorkflowVariableType.INTEGER, description="max results"),
                _var("rows", WorkflowVariableType.OBJECT, is_list=True, description="row list"),
            ],
            description="Search things.",
        )
        text = adapter._build_tool_description(tool)

        assert "    query (string): q" in text
        assert "    tags (list[string]): filters" in text
        assert "    limit (integer): max results" in text
        assert "    rows (list[object]): row list" in text


class TestReturns:
    def test_omits_returns_block_when_no_output(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        text = adapter._build_tool_description(_tool([], description="No output."))
        assert "Returns:" not in text

    def test_includes_returns_block_when_output_present(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [],
            description="Fetch item.",
            returns=[_var("item", WorkflowVariableType.OBJECT, description="fetched item")],
        )
        text = adapter._build_tool_description(tool)

        assert text.splitlines() == [
            "Fetch item.",
            "",
            "Returns:",
            "    item (object): fetched item",
        ]

    def test_args_and_returns_coexist(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [_var("q", WorkflowVariableType.STRING, description="query")],
            description="Search.",
            returns=[_var("hits", WorkflowVariableType.OBJECT, is_list=True, description="matches")],
        )
        text = adapter._build_tool_description(tool)

        assert text.splitlines() == [
            "Search.",
            "",
            "Args:",
            "    q (string): query",
            "",
            "Returns:",
            "    hits (list[object]): matches",
        ]

    def test_anonymous_return_falls_back_to_output(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [],
            description="Compute.",
            returns=[_var(None, WorkflowVariableType.NUMBER, description="the result")],
        )
        text = adapter._build_tool_description(tool)

        assert "    output (number): the result" in text

    def test_return_list_notation_matches_args(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        tool = _tool(
            [],
            returns=[_var("tags", WorkflowVariableType.STRING, is_list=True, description="labels")],
        )
        text = adapter._build_tool_description(tool)

        assert "    tags (list[string]): labels" in text

    def test_variable_group_return_rendered_as_list_of_objects_with_nested_fields(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        group = WorkflowVariableGroupConfig(
            name="pair",
            variables=[
                _var("left", WorkflowVariableType.NUMBER, description="x"),
                _var("right", WorkflowVariableType.NUMBER, description="y"),
            ],
        )
        tool = _tool([], description="Pair.", returns=[group])
        text = adapter._build_tool_description(tool)

        assert text.splitlines() == [
            "Pair.",
            "",
            "Returns:",
            "    pair (list[object]): each item has:",
            "        left (number): x",
            "        right (number): y",
        ]

    def test_variable_group_return_uses_output_fallback_when_group_unnamed(
        self, adapter: McpServerControllerAdapterService
    ) -> None:
        group = WorkflowVariableGroupConfig(
            name=None,
            variables=[_var("field", WorkflowVariableType.STRING, description="f")],
        )
        tool = _tool([], returns=[group])
        text = adapter._build_tool_description(tool)

        assert "    output (list[object]): each item has:" in text
        assert "        field (string): f" in text
