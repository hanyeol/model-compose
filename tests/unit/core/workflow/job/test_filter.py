"""Unit tests for FilterJob.

Uses a minimal in-memory JobContext stand-in that replicates:
- `register_source(scope, key, value)` — scoped source dict
- `_resolve_source(key, index, scope)` — same semantics as the real JobContext
- `render_variable(scope, value)` — a real VariableRenderer wired to `_resolve_source`

That gives us end-to-end fidelity for the ${item.*} / ${output} plumbing without
having to build up a WorkflowContext, event notifiers, etc.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl.filter import FilterJob
from mindor.dsl.schema.job import JobConfig, FilterJobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeJobContext:
    def __init__(self, workflow_input: Optional[Dict[str, Any]] = None):
        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self._workflow_input = workflow_input or {}
        self.renderer = VariableRenderer(self._resolve_source)

    def register_source(self, scope: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(scope or "__global__", {})[key] = source

    async def render_variable(self, scope: Optional[str], value: Any, skip_decode: bool = False) -> Any:
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            value = sources[key]
            return value[index] if index is not None and isinstance(value, list) else value
        if key == "input":
            return self._workflow_input
        return None


def _cfg(raw: dict) -> FilterJobConfig:
    return TypeAdapter(JobConfig).validate_python({ "type": "filter", **raw })


def _make_job(cfg: FilterJobConfig) -> FilterJob:
    job = FilterJob.__new__(FilterJob)
    job.id = "test-filter"
    job.config = cfg
    job.global_configs = None
    return job


async def _run(cfg_dict: dict, sources: Optional[Dict[str, Any]] = None) -> Any:
    context = FakeJobContext()
    for k, v in (sources or {}).items():
        context.register_source(None, k, v)
    job = _make_job(_cfg(cfg_dict))
    return await job.run(context)


# ------------------------------------------------------------------ #
# Source list handling                                               #
# ------------------------------------------------------------------ #

class TestSourceList:

    @pytest.mark.anyio
    async def test_empty_list_no_where_returns_empty(self):
        result = await _run({"input": "${source}"}, {"source": []})
        assert result == []

    @pytest.mark.anyio
    async def test_no_where_keeps_all(self):
        result = await _run({"input": "${source}"}, {"source": [1, 2, 3]})
        assert result == [1, 2, 3]

    @pytest.mark.anyio
    async def test_none_source_raises(self):
        with pytest.raises(TypeError):
            await _run({"input": "${missing}"})

    @pytest.mark.anyio
    async def test_non_list_source_raises(self):
        with pytest.raises(TypeError):
            await _run({"input": "${source}"}, {"source": {"not": "a list"}})


# ------------------------------------------------------------------ #
# Predicate evaluation                                               #
# ------------------------------------------------------------------ #

class TestWhereBasic:

    @pytest.mark.anyio
    async def test_eq_scalar(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "eq", "value": 2},
            },
            {"source": [1, 2, 3, 2]},
        )
        assert result == [2, 2]

    @pytest.mark.anyio
    async def test_gte_scalar(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "gte", "value": 3},
            },
            {"source": [1, 2, 3, 4]},
        )
        assert result == [3, 4]

    @pytest.mark.anyio
    async def test_neq_scalar(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "neq", "value": 2},
            },
            {"source": [1, 2, 3, 2]},
        )
        assert result == [1, 3]

    @pytest.mark.anyio
    async def test_no_match_returns_empty(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "eq", "value": 999},
            },
            {"source": [1, 2, 3]},
        )
        assert result == []

    @pytest.mark.anyio
    async def test_all_match_returns_all(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "gte", "value": 0},
            },
            {"source": [1, 2, 3]},
        )
        assert result == [1, 2, 3]


class TestWhereItemFieldAccess:
    """where.input can navigate into the item using ${item.path.to.field}."""

    @pytest.mark.anyio
    async def test_field_access(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item.score}", "operator": "gte", "value": 0.5},
            },
            {"source": [
                {"score": 0.1, "id": "a"},
                {"score": 0.7, "id": "b"},
                {"score": 0.5, "id": "c"},
            ]},
        )
        assert [r["id"] for r in result] == ["b", "c"]

    @pytest.mark.anyio
    async def test_nested_field_access(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item.hits[0].score}", "operator": "gt", "value": 0.4},
            },
            {"source": [
                {"hits": [{"score": 0.9}], "id": "a"},
                {"hits": [{"score": 0.2}], "id": "b"},
                {"hits": [{"score": 0.5}], "id": "c"},
            ]},
        )
        assert [r["id"] for r in result] == ["a", "c"]

    @pytest.mark.anyio
    async def test_where_value_can_reference_item(self):
        """Both sides of the comparison can be per-item expressions."""
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item.score}", "operator": "gte", "value": "${item.threshold}"},
            },
            {"source": [
                {"score": 0.9, "threshold": 0.5, "id": "a"},
                {"score": 0.1, "threshold": 0.5, "id": "b"},
                {"score": 0.5, "threshold": 0.7, "id": "c"},
            ]},
        )
        assert [r["id"] for r in result] == ["a"]


# ------------------------------------------------------------------ #
# Output rendering                                                   #
# ------------------------------------------------------------------ #

class TestOutputTemplate:

    @pytest.mark.anyio
    async def test_output_defaults_to_kept_list(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "gt", "value": 1},
            },
            {"source": [1, 2, 3]},
        )
        assert result == [2, 3]

    @pytest.mark.anyio
    async def test_output_string_expression_renders_against_result(self):
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item}", "operator": "gt", "value": 1},
                "output": "${output}",
            },
            {"source": [1, 2, 3]},
        )
        assert result == [2, 3]

    @pytest.mark.anyio
    async def test_output_map_projection(self):
        """Renderer's map syntax `"*": ${output}` iterates the kept items with fresh ${item}."""
        result = await _run(
            {
                "input": "${source}",
                "where": {"input": "${item.score}", "operator": "gte", "value": 0.5},
                "output": {
                    "*": "${output}",
                    "id": "${item.id}",
                    "score": "${item.score}",
                },
            },
            {"source": [
                {"score": 0.1, "id": "a"},
                {"score": 0.7, "id": "b"},
                {"score": 0.5, "id": "c"},
            ]},
        )
        assert result == [
            {"id": "b", "score": 0.7},
            {"id": "c", "score": 0.5},
        ]

    @pytest.mark.anyio
    async def test_output_dict_no_map(self):
        result = await _run(
            {
                "input": "${source}",
                "output": {"count": "${output}"},
            },
            {"source": [1, 2, 3]},
        )
        assert result == {"count": [1, 2, 3]}
