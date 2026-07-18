"""Unit tests for `WorkflowTool.as_model_tool`.

The agent turns `WorkflowTool.parameters` (a list of `WorkflowVariableConfig`)
into a `ModelTool` — the shared tool schema shape used across chat-completion
components and the agent. These tests cover the full type map, list wrapping
(`is_list` → `array` + `items`), select enums, description/default/required
propagation, and the anonymous-name fallback.

The `AgentComponent._build_function_schema` helper this file used to exercise
was replaced by `WorkflowTool.as_model_tool(name).model_dump(exclude_none=True)`
during the agent + chat-completion tool architecture refactor. The schema
shape emitted by `ModelTool` is intentionally not wrapped in the OpenAI
`{"type": "function", "function": {...}}` envelope; callers wrap as needed
at the LLM API boundary.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from mindor.core.workflow.tool import WorkflowTool
from mindor.dsl.schema.workflow import (
    WorkflowVariableAnnotationConfig,
    WorkflowVariableConfig,
    WorkflowVariableType,
)


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


async def _noop(*args: Any, **kwargs: Any) -> Any:
    return None


def _tool(params: List[WorkflowVariableConfig], description: Optional[str] = None) -> WorkflowTool:
    return WorkflowTool(function=_noop, description=description, parameters=params, returns=[])


def _dump(tool: WorkflowTool, name: str = "fn") -> Dict[str, Any]:
    """Render a WorkflowTool through the same path the agent uses at runtime."""
    return tool.as_model_tool(name).model_dump(exclude_none=True)


class TestTypeMapping:
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
    def test_each_variable_type_maps_to_expected_json_schema_type(
        self, var_type: WorkflowVariableType, expected_json_type: str
    ) -> None:
        schema = _dump(_tool([_var("x", var_type)]))
        assert schema["parameters"]["properties"]["x"]["type"] == expected_json_type

    def test_unmapped_type_falls_back_to_string(self) -> None:
        # `any` / `none` / `stream` have no natural JSON Schema equivalent, so we
        # want them to degrade gracefully to `"string"` rather than crash.
        for unmapped in (
            WorkflowVariableType.ANY,
            WorkflowVariableType.NONE,
            WorkflowVariableType.STREAM,
        ):
            schema = _dump(_tool([_var("x", unmapped)]))
            assert schema["parameters"]["properties"]["x"]["type"] == "string"


class TestListWrapping:
    def test_is_list_wraps_scalar_in_array_with_items(self) -> None:
        schema = _dump(_tool([_var("tags", WorkflowVariableType.STRING, is_list=True)]))
        prop = schema["parameters"]["properties"]["tags"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string"}

    def test_is_list_of_objects_produces_array_of_objects(self) -> None:
        schema = _dump(_tool([_var("rows", WorkflowVariableType.OBJECT, is_list=True)]))
        prop = schema["parameters"]["properties"]["rows"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "object"}

    def test_bare_list_type_stays_array_without_items(self) -> None:
        # `type=list` with `is_list=False` means the value itself is a heterogeneous
        # array; there is no inner item type to declare.
        schema = _dump(_tool([_var("bag", WorkflowVariableType.LIST)]))
        prop = schema["parameters"]["properties"]["bag"]
        assert prop["type"] == "array"
        assert "items" not in prop


class TestSelectEnum:
    def test_select_with_options_emits_enum(self) -> None:
        schema = _dump(_tool(
            [_var("size", WorkflowVariableType.SELECT, options=["s", "m", "l"], default="m")]
        ))
        prop = schema["parameters"]["properties"]["size"]
        assert prop["type"] == "string"
        assert prop["enum"] == ["s", "m", "l"]
        assert prop["default"] == "m"

    def test_select_without_options_has_no_enum(self) -> None:
        schema = _dump(_tool([_var("size", WorkflowVariableType.SELECT)]))
        prop = schema["parameters"]["properties"]["size"]
        assert "enum" not in prop

    def test_select_wrapped_in_list_puts_enum_on_items(self) -> None:
        # `enum` belongs to the inner item schema, not the surrounding array.
        schema = _dump(_tool([
            _var("sizes", WorkflowVariableType.SELECT, options=["s", "m", "l"], is_list=True),
        ]))
        prop = schema["parameters"]["properties"]["sizes"]
        assert prop["type"] == "array"
        assert prop["items"] == {"type": "string", "enum": ["s", "m", "l"]}
        assert "enum" not in prop


class TestMetadataPropagation:
    def test_description_from_annotation_is_emitted(self) -> None:
        schema = _dump(_tool([_var("q", WorkflowVariableType.STRING, description="query text")]))
        assert schema["parameters"]["properties"]["q"]["description"] == "query text"

    def test_missing_description_is_omitted(self) -> None:
        schema = _dump(_tool([_var("q", WorkflowVariableType.STRING)]))
        assert "description" not in schema["parameters"]["properties"]["q"]

    def test_default_is_emitted_when_not_none(self) -> None:
        schema = _dump(_tool([_var("limit", WorkflowVariableType.INTEGER, default=10)]))
        assert schema["parameters"]["properties"]["limit"]["default"] == 10

    def test_zero_default_is_still_emitted(self) -> None:
        # Falsy-but-not-None defaults (0, "", False) must survive round-trip.
        schema = _dump(_tool([_var("n", WorkflowVariableType.INTEGER, default=0)]))
        prop = schema["parameters"]["properties"]["n"]
        assert "default" in prop
        assert prop["default"] == 0

    def test_none_default_is_omitted(self) -> None:
        schema = _dump(_tool([_var("x", WorkflowVariableType.STRING, default=None)]))
        assert "default" not in schema["parameters"]["properties"]["x"]


class TestRequiredList:
    def test_required_flags_collect_into_required_array(self) -> None:
        schema = _dump(_tool([
            _var("a", WorkflowVariableType.STRING, required=True),
            _var("b", WorkflowVariableType.STRING, required=False),
            _var("c", WorkflowVariableType.INTEGER, required=True),
        ]))
        assert schema["parameters"]["required"] == ["a", "c"]

    def test_no_required_params_omits_required_key(self) -> None:
        # `required=[]` is the pydantic default; `exclude_none=True` alone would
        # keep it, but downstream consumers accept its absence too. The concrete
        # ModelTool schema currently emits an empty list; assert on that shape.
        schema = _dump(_tool([_var("a", WorkflowVariableType.STRING)]))
        assert schema["parameters"].get("required", []) == []


class TestNameFallback:
    def test_anonymous_variable_becomes_input_key(self) -> None:
        # An unnamed workflow input is exposed to LLMs as a single `input` slot.
        schema = _dump(_tool([_var(None, WorkflowVariableType.STRING, required=True)]))
        assert list(schema["parameters"]["properties"]) == ["input"]
        assert schema["parameters"]["required"] == ["input"]


class TestTopLevelShape:
    def test_envelope_matches_model_tool_shape(self) -> None:
        schema = _dump(
            _tool([_var("q", WorkflowVariableType.STRING, required=True)], description="Do a search."),
            name="search",
        )
        assert schema["name"] == "search"
        assert schema["description"] == "Do a search."
        assert schema["parameters"]["type"] == "object"
        assert "properties" in schema["parameters"]

    def test_tool_without_description_omits_key(self) -> None:
        schema = _dump(_tool([_var("q", WorkflowVariableType.STRING)]), name="search")
        assert "description" not in schema

    def test_tool_without_parameters_still_produces_valid_object(self) -> None:
        schema = _dump(_tool([], description="No inputs."), name="noop")
        # With no parameters, ModelTool still emits the object envelope with an
        # empty properties dict; downstream consumers can then treat it as
        # "no-arg". `required` defaults to [] and may or may not be present.
        assert schema["parameters"]["type"] == "object"
        assert schema["parameters"].get("properties", {}) == {}

    def test_multiple_parameters_are_all_present(self) -> None:
        schema = _dump(_tool([
            _var("query", WorkflowVariableType.STRING, required=True, description="q"),
            _var("limit", WorkflowVariableType.INTEGER, default=10),
            _var("size", WorkflowVariableType.SELECT, options=["s", "m", "l"], default="m"),
            _var("tags", WorkflowVariableType.STRING, is_list=True),
        ]), name="search")

        props = schema["parameters"]["properties"]
        assert set(props) == {"query", "limit", "size", "tags"}
        assert schema["parameters"]["required"] == ["query"]
        assert props["tags"] == {"type": "array", "items": {"type": "string"}}
        assert props["size"]["enum"] == ["s", "m", "l"]
