"""Unit tests for DelayJob.

Focus is on the `is_direct_output` fast path introduced in `DelayJob.run`:
- No `output` configured -> raw output (None from `_delay`) is returned as-is
- `output: "${output}"` -> also a fast path; no register/render pass
- Any other `output` template -> render pass runs and `output` source is registered
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl.delay import DelayJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeWorkflow:
    def __init__(self):
        self.task_id = "task-test"
        self.workflow_id = "wf-test"


class FakeJobContext:
    def __init__(self):
        self.workflow = FakeWorkflow()
        self.is_terminal = False
        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self.renderer = VariableRenderer(self._resolve_source)
        self.register_calls: list[tuple[Optional[str], str, Any]] = []

    def register_source(self, scope: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(scope or "__global__", {})[key] = source
        self.register_calls.append((scope, key, source))

    async def render_variable(self, scope: Optional[str], value: Any, skip_decode: bool = False) -> Any:
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            value = sources[key]
            return value[index] if index is not None and isinstance(value, list) else value
        return None


def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python({ "type": "delay", "mode": "time-interval", **raw })


def _make_job(cfg) -> DelayJob:
    job = DelayJob.__new__(DelayJob)
    job.id = "test-delay"
    job.config = cfg
    job.global_configs = None
    return job


def _output_registered(context: FakeJobContext) -> bool:
    return any(
        key == "output" and (scope is None or scope == "__global__")
        for scope, key, _ in context.register_calls
    )


class TestDelayOutputFastPath:

    @pytest.mark.anyio
    async def test_output_not_specified_returns_none_direct(self):
        # No `output` -> fast path. DelayJob._delay returns None, and no render
        # / register happens for `output`.
        context = FakeJobContext()
        job = _make_job(_cfg({"duration": 0}))

        result = await job.run(context)

        assert result is None
        assert not _output_registered(context)

    @pytest.mark.anyio
    async def test_output_explicit_dollar_output_is_direct(self):
        # `output: "${output}"` also fast paths -> returned value is the raw
        # `_delay` result (None) and no register_source call for `output`.
        context = FakeJobContext()
        job = _make_job(_cfg({"duration": 0, "output": "${output}"}))

        result = await job.run(context)

        assert result is None
        assert not _output_registered(context)

    @pytest.mark.anyio
    async def test_output_dict_template_renders(self):
        # Non-passthrough `output` triggers the render path: `output` gets
        # registered on the global scope and the template is materialized.
        context = FakeJobContext()
        job = _make_job(_cfg({"duration": 0, "output": {"marker": "done"}}))

        result = await job.run(context)

        assert result == {"marker": "done"}
        assert _output_registered(context)
