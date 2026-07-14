"""Unit tests for ComponentJob.

Focus is on the `is_direct_output` fast path in `ComponentJob._run`. The
component itself is stubbed by monkeypatching `_create_component`.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl.component import ComponentJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeWorkflow:
    def __init__(self, workflow_input: Optional[Any] = None):
        self.task_id = "task-test"
        self.workflow_id = "wf-test"
        self.input = workflow_input
        self.run_ids: List[tuple[str, str]] = []

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.run_ids.append((job_id, run_id))


class FakeJobContext:
    def __init__(self, workflow_input: Optional[Any] = None):
        self.workflow = FakeWorkflow(workflow_input)
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


class FakeComponent:
    def __init__(self, result: Any):
        self.id = "fake-component"
        self.started = True
        self._result = result
        self.calls: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self.started = True

    async def run(self, action, run_id, input, workflow, job_id):
        self.calls.append({
            "action": action, "run_id": run_id, "input": input, "job_id": job_id,
        })
        return self._result


def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python({ "type": "component", **raw })


def _make_job(cfg, component: FakeComponent) -> ComponentJob:
    job = ComponentJob.__new__(ComponentJob)
    job.id = "test-component"
    job.config = cfg
    job.global_configs = None
    job._create_component = lambda _id, _component: component  # type: ignore[assignment]
    return job


def _run_output_registered(context: FakeJobContext) -> bool:
    """True if _run scoped a `output` under its run_id (i.e. render path taken)."""
    return any(
        key == "output" and scope not in (None, "__global__")
        for scope, key, _ in context.register_calls
    )


class TestComponentJobOutputFastPath:

    @pytest.mark.anyio
    async def test_run_output_direct_fast_path(self):
        # No `output` -> the component result flows through unchanged and no
        # per-run `output` render happens.
        context = FakeJobContext(workflow_input={"q": "hi"})
        component = FakeComponent(result={"stdout": "hello", "code": 0})
        job = _make_job(
            _cfg({"component": "c", "action": "a"}),
            component,
        )

        result = await job.run(context)

        assert result == {"stdout": "hello", "code": 0}
        assert not _run_output_registered(context)

    @pytest.mark.anyio
    async def test_run_output_explicit_dollar_is_direct(self):
        # `output: "${output}"` is a fast path: raw component result returned.
        context = FakeJobContext(workflow_input={"q": "hi"})
        component = FakeComponent(result={"stdout": "hello"})
        job = _make_job(
            _cfg({"component": "c", "action": "a", "output": "${output}"}),
            component,
        )

        result = await job.run(context)

        assert result == {"stdout": "hello"}
        assert not _run_output_registered(context)

    @pytest.mark.anyio
    async def test_run_output_template_renders(self):
        # A dict template with a field-access reference should render against
        # the per-run `output` source and produce the wrapped shape.
        context = FakeJobContext(workflow_input={"q": "hi"})
        component = FakeComponent(result={"stdout": "hello", "code": 0})
        job = _make_job(
            _cfg({
                "component": "c",
                "action": "a",
                "output": {"result": "${output.stdout}"},
            }),
            component,
        )

        result = await job.run(context)

        assert result == {"result": "hello"}
        assert _run_output_registered(context)
