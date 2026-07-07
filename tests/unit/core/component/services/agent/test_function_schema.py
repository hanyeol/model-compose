"""Unit tests for `AgentComponent._build_function_schema`.

The agent turns `WorkflowTool.parameters` (a list of `WorkflowVariableConfig`)
into an OpenAI-compatible function-calling JSON Schema. These tests cover the
full type map, list wrapping (`is_list` → `array` + `items`), select enums,
description/default/required propagation, and the anonymous-name fallback.
"""

from __future__ import annotations

from typing import Any, List, Optional

import pytest

from mindor.core.component.services.agent.agent import AgentComponent
from mindor.core.workflow.tool import WorkflowTool
from mindor.dsl.schema.workflow import (
    WorkflowVariableAnnotationConfig,
    WorkflowVariableConfig,
    WorkflowVariableType,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def agent() -> AgentComponent:
    # Bypass __init__ (it requires configs); we only exercise the schema builder.
    return AgentComponent.__new__(AgentComponent)


def _var(
    name: Optional[str],
    type: WorkflowVariableType,
    *,
    is_list: bool = False,
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
        options=options,
        required=required,
        default=default,
        annotations=annotations,
    )


def _tool(params: List[WorkflowVariableConfig], description: Optional[str] = None) -> WorkflowTool:
    return WorkflowTool(function=_noop, description=description, parameters=params)


async def _noop(*args: Any, **kwargs: Any) -> Any:
    return None


class TestTypeMapping:
    @pytest.mark.anyio
    @pytest.mark.parametrize(
        "var_type, expected_json_type",
        [
            (WorkflowVariableType.STRING, "string"),
            (WorkflowVariableType.TEXT, "string"),
            (WorkflowVariableType.MARKDOWN, "string"),
            (WorkflowVariableType.BASE64, "string"),
            (WorkflowVariableType.IMAGE, "string"),
            (WorkflowVariableType.AUDIO, "string"),
            (WorkflowVariableType.VIDEO, "string"),
            (WorkflowVariableType.FILE, "string"),
            (WorkflowVariableType.SELECT, "string"),
            (WorkflowVariableType.INTEGER, "integer"),
            (WorkflowVariableType.NUMBER, "number"),
            (WorkflowVariableType.BOOLEAN, "boolean"),
            (WorkflowVariableType.LIST, "array"),
            (WorkflowVariableType.OBJECT, "object"),
            (WorkflowVariableType.JSON, "object"),
        ],
    )
    async def test_each_variable_type_maps_to_expected_json_schema_type(
        self, agent: AgentComponent, var_type: WorkflowVariableType, expected_json_type: str
    ) -> None:
        tool = _tool([_var("x", var_type)])
        schema = await agent._build_function_schema("fn", tool)

        assert schema["function"]["parameters"]["properties"]["x"]["type"] == expected_json_type

    @pytest.mark.anyio
    async def test_unmapped_type_falls_back_to_string(self, agent: AgentComponent) -> None:
        # `any` / `none` / `stream` have no natural JSON Schema equivalent, so we
        # want them to degrade gracefully to `"string"` rather than crash.
        for unmapped in (
            WorkflowVariableType.ANY,
            WorkflowVariableType.NONE,
            WorkflowVariableType.STREAM,
        ):
            tool = _tool([_var("x", unmapped)])
            schema = await agent._build_function_schema("fn", tool)
            assert schema["function"]["parameters"]["properties"]["x"]["type"] == "string"


class TestListWrapping:
    @pytest.mark.anyio
    async def test_is_list_wraps_scalar_in_array_with_items(self, agent: AgentComponent) -> None:
        tool = _tool([_var("tags", WorkflowVariableType.STRING, is_list=True)])
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["tags"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string"}

    @pytest.mark.anyio
    async def test_is_list_of_objects_produces_array_of_objects(
        self, agent: AgentComponent
    ) -> None:
        tool = _tool([_var("rows", WorkflowVariableType.OBJECT, is_list=True)])
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["rows"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "object"}

    @pytest.mark.anyio
    async def test_bare_list_type_stays_array_without_items(self, agent: AgentComponent) -> None:
        # `type=list` with `is_list=False` means the value itself is a heterogeneous
        # array; there is no inner item type to declare.
        tool = _tool([_var("bag", WorkflowVariableType.LIST)])
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["bag"]
        assert prop["type"] == "array"
        assert "items" not in prop


class TestSelectEnum:
    @pytest.mark.anyio
    async def test_select_with_options_emits_enum(self, agent: AgentComponent) -> None:
        tool = _tool(
            [_var("size", WorkflowVariableType.SELECT, options=["s", "m", "l"], default="m")]
        )
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["size"]
        assert prop["type"] == "string"
        assert prop["enum"] == ["s", "m", "l"]
        assert prop["default"] == "m"

    @pytest.mark.anyio
    async def test_select_without_options_has_no_enum(self, agent: AgentComponent) -> None:
        tool = _tool([_var("size", WorkflowVariableType.SELECT)])
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["size"]
        assert "enum" not in prop

    @pytest.mark.anyio
    async def test_select_wrapped_in_list_puts_enum_on_items(self, agent: AgentComponent) -> None:
        # `enum` belongs to the inner item schema, not the surrounding array.
        tool = _tool(
            [
                _var(
                    "sizes",
                    WorkflowVariableType.SELECT,
                    options=["s", "m", "l"],
                    is_list=True,
                )
            ]
        )
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["sizes"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string", "enum": ["s", "m", "l"]}
        assert "enum" not in prop


class TestMetadataPropagation:
    @pytest.mark.anyio
    async def test_description_from_annotation_is_emitted(self, agent: AgentComponent) -> None:
        tool = _tool([_var("q", WorkflowVariableType.STRING, description="query text")])
        schema = await agent._build_function_schema("fn", tool)

        assert (
            schema["function"]["parameters"]["properties"]["q"]["description"] == "query text"
        )

    @pytest.mark.anyio
    async def test_missing_description_is_omitted(self, agent: AgentComponent) -> None:
        tool = _tool([_var("q", WorkflowVariableType.STRING)])
        schema = await agent._build_function_schema("fn", tool)

        assert "description" not in schema["function"]["parameters"]["properties"]["q"]

    @pytest.mark.anyio
    async def test_default_is_emitted_when_not_none(self, agent: AgentComponent) -> None:
        tool = _tool([_var("limit", WorkflowVariableType.INTEGER, default=10)])
        schema = await agent._build_function_schema("fn", tool)

        assert schema["function"]["parameters"]["properties"]["limit"]["default"] == 10

    @pytest.mark.anyio
    async def test_zero_default_is_still_emitted(self, agent: AgentComponent) -> None:
        # Falsy-but-not-None defaults (0, "", False) must survive round-trip.
        tool = _tool([_var("n", WorkflowVariableType.INTEGER, default=0)])
        schema = await agent._build_function_schema("fn", tool)

        prop = schema["function"]["parameters"]["properties"]["n"]
        assert "default" in prop
        assert prop["default"] == 0

    @pytest.mark.anyio
    async def test_none_default_is_omitted(self, agent: AgentComponent) -> None:
        tool = _tool([_var("x", WorkflowVariableType.STRING, default=None)])
        schema = await agent._build_function_schema("fn", tool)

        assert "default" not in schema["function"]["parameters"]["properties"]["x"]


class TestRequiredList:
    @pytest.mark.anyio
    async def test_required_flags_collect_into_required_array(
        self, agent: AgentComponent
    ) -> None:
        tool = _tool(
            [
                _var("a", WorkflowVariableType.STRING, required=True),
                _var("b", WorkflowVariableType.STRING, required=False),
                _var("c", WorkflowVariableType.INTEGER, required=True),
            ]
        )
        schema = await agent._build_function_schema("fn", tool)

        assert schema["function"]["parameters"]["required"] == ["a", "c"]

    @pytest.mark.anyio
    async def test_no_required_params_omits_required_key(self, agent: AgentComponent) -> None:
        # OpenAI accepts absent `required`; emitting `[]` would be noisy.
        tool = _tool([_var("a", WorkflowVariableType.STRING)])
        schema = await agent._build_function_schema("fn", tool)

        assert "required" not in schema["function"]["parameters"]


class TestNameFallback:
    @pytest.mark.anyio
    async def test_anonymous_variable_becomes_input_key(self, agent: AgentComponent) -> None:
        # An unnamed workflow input is exposed to LLMs as a single `input` slot.
        tool = _tool([_var(None, WorkflowVariableType.STRING, required=True)])
        schema = await agent._build_function_schema("fn", tool)

        assert list(schema["function"]["parameters"]["properties"]) == ["input"]
        assert schema["function"]["parameters"]["required"] == ["input"]


class TestTopLevelShape:
    @pytest.mark.anyio
    async def test_envelope_matches_openai_function_calling_shape(
        self, agent: AgentComponent
    ) -> None:
        tool = _tool(
            [_var("q", WorkflowVariableType.STRING, required=True)],
            description="Do a search.",
        )
        schema = await agent._build_function_schema("search", tool)

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search"
        assert schema["function"]["description"] == "Do a search."
        assert schema["function"]["parameters"]["type"] == "object"
        assert "properties" in schema["function"]["parameters"]

    @pytest.mark.anyio
    async def test_tool_without_description_omits_key(self, agent: AgentComponent) -> None:
        tool = _tool([_var("q", WorkflowVariableType.STRING)])
        schema = await agent._build_function_schema("search", tool)

        assert "description" not in schema["function"]

    @pytest.mark.anyio
    async def test_tool_without_parameters_still_produces_valid_object(
        self, agent: AgentComponent
    ) -> None:
        tool = _tool([], description="No inputs.")
        schema = await agent._build_function_schema("noop", tool)

        assert schema["function"]["parameters"] == {"type": "object", "properties": {}}

    @pytest.mark.anyio
    async def test_multiple_parameters_are_all_present(self, agent: AgentComponent) -> None:
        tool = _tool(
            [
                _var("query", WorkflowVariableType.STRING, required=True, description="q"),
                _var("limit", WorkflowVariableType.INTEGER, default=10),
                _var(
                    "size",
                    WorkflowVariableType.SELECT,
                    options=["s", "m", "l"],
                    default="m",
                ),
                _var("tags", WorkflowVariableType.STRING, is_list=True),
            ]
        )
        schema = await agent._build_function_schema("search", tool)

        props = schema["function"]["parameters"]["properties"]
        assert set(props) == {"query", "limit", "size", "tags"}
        assert schema["function"]["parameters"]["required"] == ["query"]
        assert props["tags"] == {"type": "array", "items": {"type": "string"}}
        assert props["size"]["enum"] == ["s", "m", "l"]
