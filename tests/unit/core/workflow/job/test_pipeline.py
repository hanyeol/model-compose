"""Unit tests for PipelineJob.

Covers:
- Sequential step execution (order preserved, previous output flows to next).
- `${input}` refers to the pipeline input across all steps.
- `${output}` refers to the previous step's output (unavailable in the first step).
- `is_direct_output` fast path on the top-level `output`.
- Per-step `output` mapping transforms the value that flows into the next step.

The component is stubbed by monkeypatching `_create_component`, so we don't
need a real ComponentService wired up.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl import common as impl_common
from mindor.core.workflow.job.impl.pipeline import PipelineJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


class FakeWorkflow:
    def __init__(self):
        self.task_id = "task-test"
        self.workflow_id = "wf-test"
        self.input: Any = None
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
        effective_scope = scope or (self._run_id_stack[-1] if self._run_id_stack else None)
        return await self.renderer.render(value, effective_scope, skip_decode=skip_decode)

    async def resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
        sources = self._sources.get(scope or "__global__", {})
        if key in sources:
            value = sources[key]
            return value[index] if index is not None and isinstance(value, list) else value
        # Fall through to global so inner composites can read outer scope names.
        outer = self._sources.get("__global__", {})
        if key in outer:
            value = outer[key]
            return value[index] if index is not None and isinstance(value, list) else value
        return None


class FakeComponent:
    """Minimal ComponentService stand-in.

    `run(action, run_id, input, workflow, job_id)` echoes the input by default,
    or applies `transform` if provided.
    """
    def __init__(self, transform=None, tag: str = "fake"):
        self.id = f"fake-{tag}"
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
    return TypeAdapter(JobConfig).validate_python({ "type": "pipeline", **raw })


def _make_job(cfg, per_step_component, monkeypatch: Optional[pytest.MonkeyPatch] = None) -> PipelineJob:
    """Create a PipelineJob whose `_create_component` (and every inline
    sub-job's `_create_component`) returns the next component from
    `per_step_component` on each call.

    `monkeypatch` is required to intercept `create_job` so that inline
    ComponentJob instances also route through the fake component factory.
    """
    if callable(per_step_component):
        _create_component = per_step_component
    else:
        it = iter(per_step_component)
        async def _create_component(_id, _component):
            return next(it)

    if monkeypatch is not None:
        original_create_job = impl_common.create_job

        def wrapped_create_job(job_id, config, global_configs):
            inline_job = original_create_job(job_id, config, global_configs)
            if hasattr(inline_job, "_create_component"):
                inline_job._create_component = _create_component  # type: ignore[assignment]
            return inline_job

        monkeypatch.setattr(impl_common, "create_job", wrapped_create_job)

    job = PipelineJob.__new__(PipelineJob)
    job.id = "test-pipeline"
    job.config = cfg
    job.global_configs = None
    job._create_component = _create_component  # type: ignore[assignment]

    return job


def _output_registered_on_global(context: FakeJobContext) -> bool:
    return any(
        key == "output" and (scope is None or scope == "__global__")
        for scope, key, _ in context.register_calls
    )


class TestSequentialExecution:

    @pytest.mark.anyio
    async def test_first_step_receives_pipeline_input_via_input(self, monkeypatch):
        # `${input}` in the first step should resolve to the pipeline input.
        context = FakeJobContext()
        component = FakeComponent()
        job = _make_job(
            _cfg({
                "input": "hello",
                "steps": [
                    { "component": "c", "action": "a", "input": "${input}" },
                ],
            }),
            [component],
            monkeypatch,
        )

        result = await job.run(context)

        assert result == "hello"
        assert component.calls[0]["input"] == "hello"

    @pytest.mark.anyio
    async def test_second_step_receives_first_output_via_output(self, monkeypatch):
        # `${output}` in step 2 should resolve to the output of step 1.
        context = FakeJobContext()
        c1 = FakeComponent(transform=lambda x: f"[{x}]", tag="1")
        c2 = FakeComponent(transform=lambda x: f"<{x}>", tag="2")

        job = _make_job(
            _cfg({
                "input": "a",
                "steps": [
                    { "component": "c1", "action": "op", "input": "${input}" },
                    { "component": "c2", "action": "op", "input": "${output}" },
                ],
            }),
            [c1, c2],
            monkeypatch,
        )

        result = await job.run(context)

        assert c1.calls[0]["input"] == "a"
        assert c2.calls[0]["input"] == "[a]"
        assert result == "<[a]>"

    @pytest.mark.anyio
    async def test_step_defaults_input_to_previous_output_when_input_omitted(self, monkeypatch):
        # When step.input is None (not set), it should default to:
        #   - pipeline input for step 0
        #   - previous output for steps > 0
        context = FakeJobContext()
        c1 = FakeComponent(transform=lambda x: f"step1({x})", tag="1")
        c2 = FakeComponent(transform=lambda x: f"step2({x})", tag="2")

        job = _make_job(
            _cfg({
                "input": "seed",
                "steps": [
                    { "component": "c1", "action": "op" },  # no input -> pipeline input
                    { "component": "c2", "action": "op" },  # no input -> step1 output
                ],
            }),
            [c1, c2],
            monkeypatch,
        )

        result = await job.run(context)

        assert c1.calls[0]["input"] == "seed"
        assert c2.calls[0]["input"] == "step1(seed)"
        assert result == "step2(step1(seed))"

    @pytest.mark.anyio
    async def test_three_step_chaining(self, monkeypatch):
        context = FakeJobContext()
        c1 = FakeComponent(transform=lambda x: x + 1, tag="1")
        c2 = FakeComponent(transform=lambda x: x * 10, tag="2")
        c3 = FakeComponent(transform=lambda x: -x, tag="3")

        job = _make_job(
            _cfg({
                "input": 5,
                "steps": [
                    { "component": "c1", "action": "op", "input": "${input}" },
                    { "component": "c2", "action": "op", "input": "${output}" },
                    { "component": "c3", "action": "op", "input": "${output}" },
                ],
            }),
            [c1, c2, c3],
            monkeypatch,
        )

        result = await job.run(context)

        assert c1.calls[0]["input"] == 5
        assert c2.calls[0]["input"] == 6
        assert c3.calls[0]["input"] == 60
        assert result == -60


class TestOutputFastPath:

    @pytest.mark.anyio
    async def test_no_top_output_returns_last_step_verbatim(self, monkeypatch):
        context = FakeJobContext()
        c1 = FakeComponent()
        job = _make_job(
            _cfg({
                "input": "x",
                "steps": [
                    { "component": "c", "action": "a", "input": "${input}" },
                ],
            }),
            [c1],
            monkeypatch,
        )

        result = await job.run(context)

        assert result == "x"
        assert not _output_registered_on_global(context)

    @pytest.mark.anyio
    async def test_explicit_dollar_output_is_direct(self, monkeypatch):
        context = FakeJobContext()
        c1 = FakeComponent()
        job = _make_job(
            _cfg({
                "input": "x",
                "output": "${output}",
                "steps": [
                    { "component": "c", "action": "a", "input": "${input}" },
                ],
            }),
            [c1],
            monkeypatch,
        )

        result = await job.run(context)

        assert result == "x"
        assert not _output_registered_on_global(context)

    @pytest.mark.anyio
    async def test_output_template_renders(self, monkeypatch):
        context = FakeJobContext()
        c1 = FakeComponent(transform=lambda x: f"[{x}]")
        job = _make_job(
            _cfg({
                "input": "hi",
                "output": { "wrapped": "${output}" },
                "steps": [
                    { "component": "c", "action": "a", "input": "${input}" },
                ],
            }),
            [c1],
            monkeypatch,
        )

        result = await job.run(context)

        assert result == { "wrapped": "[hi]" }
        assert _output_registered_on_global(context)


class TestStepOutputMapping:

    @pytest.mark.anyio
    async def test_step_output_transforms_value_flowing_to_next(self, monkeypatch):
        # step[0].output remaps the raw component result before it becomes
        # the previous_output that step[1] sees as ${output}.
        context = FakeJobContext()
        c1 = FakeComponent(transform=lambda x: { "id": x, "extra": 42 })
        c2 = FakeComponent(transform=lambda x: f"got:{x}")

        job = _make_job(
            _cfg({
                "input": "seed",
                "steps": [
                    {
                        "component": "c1",
                        "action": "a",
                        "input": "${input}",
                        "output": "${output.id}",  # extract just the id
                    },
                    { "component": "c2", "action": "a", "input": "${output}" },
                ],
            }),
            [c1, c2],
            monkeypatch,
        )

        result = await job.run(context)

        # step2 should have received the transformed value ("seed"), not the raw dict
        assert c2.calls[0]["input"] == "seed"
        assert result == "got:seed"
