"""Unit tests for ForEachJob.

Covers the `is_direct_output` fast paths introduced in both `ForEachJob.run`
(top-level `output`) and `ForEachJob._run` (per-iteration `do.output`).

The component is stubbed by monkeypatching `_create_component`, so we don't
need a real ComponentService wired up.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl.for_each import ForEachJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeWorkflow:
    def __init__(self):
        self.task_id = "task-test"
        self.workflow_id = "wf-test"
        self.run_ids: List[tuple[str, str]] = []

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.run_ids.append((job_id, run_id))


class FakeJobContext:
    def __init__(self):
        self.workflow = FakeWorkflow()
        self._is_terminal = False
        self.cancellation_token = None
        self._sources: Dict[str, Dict[str, Any]] = { "__global__": {} }
        self._run_id_stack: List[str] = []
        self._default_input_stack: List[Any] = []
        self._is_terminal_stack: List[bool] = []
        self.renderer = VariableRenderer(self.resolve_source)
        self.register_calls: list[tuple[Optional[str], str, Any]] = []

    @property
    def default_input(self) -> Any:
        if self._default_input_stack and self._default_input_stack[-1] is not None:
            return self._default_input_stack[-1]
        return getattr(self.workflow, "input", None)

    @property
    def is_terminal(self) -> bool:
        if self._is_terminal_stack:
            return self._is_terminal_stack[-1]
        return self._is_terminal

    @is_terminal.setter
    def is_terminal(self, value: bool) -> None:
        self._is_terminal = value

    class _InlineScope:
        def __init__(self, context: "FakeJobContext", run_id: str, default_input: Any, is_terminal: bool) -> None:
            self._context = context
            self._run_id = run_id
            self._default_input = default_input
            self._is_terminal = is_terminal
        def __enter__(self) -> None:
            self._context._run_id_stack.append(self._run_id)
            self._context._default_input_stack.append(self._default_input)
            self._context._is_terminal_stack.append(self._is_terminal)
        def __exit__(self, *_exc) -> None:
            self._context._run_id_stack.pop()
            self._context._default_input_stack.pop()
            self._context._is_terminal_stack.pop()

    def use_inline_scope(self, run_id: str, default_input: Any = None, is_terminal: bool = False):
        return self._InlineScope(self, run_id, default_input, is_terminal)

    def register_source(self, scope: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(scope or "__global__", {})[key] = source
        self.register_calls.append((scope, key, source))

    async def render_variable(self, scope: Optional[str], value: Any, skip_decode: bool = False) -> Any:
        return await self.renderer.render(value, scope, skip_decode=skip_decode)

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            value = sources[key]
            return value[index] if index is not None and isinstance(value, list) else value
        return None


class FakeComponent:
    """Minimal ComponentService stand-in.

    `run(action, run_id, input, workflow, job_id)` echoes the input by default,
    or applies `transform` if provided.
    """
    def __init__(self, transform=None):
        self.id = "fake-component"
        self.started = True
        self._transform = transform
        self.calls: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self.started = True

    async def run(self, action, run_id, input, workflow, job_id):
        self.calls.append({
            "action": action, "run_id": run_id, "input": input, "job_id": job_id,
        })
        return self._transform(input) if self._transform else input


def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python({ "type": "for-each", **raw })


def _make_job(cfg, component: FakeComponent, monkeypatch: Optional[pytest.MonkeyPatch] = None) -> ForEachJob:
    async def _create_component(_id, _component):
        return component

    if monkeypatch is not None:
        from mindor.core.workflow.job.impl import common as impl_common
        original_create_job = impl_common.create_job

        def wrapped_create_job(job_id, config, global_configs):
            inline_job = original_create_job(job_id, config, global_configs)
            if hasattr(inline_job, "_create_component"):
                inline_job._create_component = _create_component  # type: ignore[assignment]
            return inline_job

        monkeypatch.setattr(impl_common, "create_job", wrapped_create_job)

    job = ForEachJob.__new__(ForEachJob)
    job.id = "test-for-each"
    job.config = cfg
    job.global_configs = None
    job._create_component = _create_component  # type: ignore[assignment]
    return job


def _output_registered(context: FakeJobContext) -> bool:
    return any(
        key == "output" and (scope is None or scope == "__global__")
        for scope, key, _ in context.register_calls
    )


# ------------------------------------------------------------------ #
# Top-level `output` fast path                                       #
# ------------------------------------------------------------------ #

class TestRunOutputFastPath:

    @pytest.mark.anyio
    async def test_run_output_direct_fast_path(self, monkeypatch):
        # No top-level `output` -> the iteration result list is returned
        # verbatim and no global `output` source is registered.
        context = FakeJobContext()
        component = FakeComponent()
        job = _make_job(
            _cfg({
                "input": [1, 2, 3],
                "do": { "component": "c", "action": "a" },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == [1, 2, 3]
        assert not _output_registered(context)

    @pytest.mark.anyio
    async def test_run_output_explicit_dollar_is_direct(self, monkeypatch):
        # `output: "${output}"` still bypasses the render pass.
        context = FakeJobContext()
        component = FakeComponent()
        job = _make_job(
            _cfg({
                "input": [10, 20],
                "output": "${output}",
                "do": { "component": "c", "action": "a" },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == [10, 20]
        assert not _output_registered(context)

    @pytest.mark.anyio
    async def test_run_output_template_renders(self, monkeypatch):
        # A non-passthrough `output` template should trigger the render pass,
        # register `output` on the global scope, and materialize the wrapper.
        context = FakeJobContext()
        component = FakeComponent()
        job = _make_job(
            _cfg({
                "input": [1, 2, 3],
                "output": {"items": "${output}"},
                "do": { "component": "c", "action": "a" },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == {"items": [1, 2, 3]}
        assert _output_registered(context)


# ------------------------------------------------------------------ #
# Per-iteration `do.output` fast path                                #
# ------------------------------------------------------------------ #

class TestDoOutputFastPath:

    @pytest.mark.anyio
    async def test_do_output_direct_fast_path(self, monkeypatch):
        # `do.output` unset -> per-iteration raw component output is returned.
        context = FakeJobContext()
        component = FakeComponent(transform=lambda x: {"value": x})
        job = _make_job(
            _cfg({
                "input": [1, 2],
                "do": { "component": "c", "action": "a" },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == [{"value": 1}, {"value": 2}]

    @pytest.mark.anyio
    async def test_do_output_explicit_dollar_is_direct(self, monkeypatch):
        # `do.output: "${output}"` is also a fast path: raw component output
        # is returned per iteration.
        context = FakeJobContext()
        component = FakeComponent(transform=lambda x: {"value": x})
        job = _make_job(
            _cfg({
                "input": [1, 2],
                "do": {
                    "component": "c",
                    "action": "a",
                    "output": "${output}",
                },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == [{"value": 1}, {"value": 2}]

    @pytest.mark.anyio
    async def test_do_output_template_renders(self, monkeypatch):
        # `do.output` template triggers per-iteration render: each raw output
        # is wrapped by the template.
        context = FakeJobContext()
        component = FakeComponent()  # identity transform
        job = _make_job(
            _cfg({
                "input": ["a", "b"],
                "do": {
                    "component": "c",
                    "action": "a",
                    "output": {"wrapped": "${output}"},
                },
            }),
            component,
            monkeypatch,
        )

        result = await job.run(context)

        assert result == [{"wrapped": "a"}, {"wrapped": "b"}]
