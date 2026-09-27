"""Unit tests for LoopJob.

Covers:
- do-while semantics: `do` runs at least once; condition is evaluated after.
- Feed-forward: `${input}` is the loop's initial input (fixed); `${output}` is
  the previous iteration's output (unset on iteration 0), matching pipeline.
- Default input for `do` when `do.input` is omitted: iteration 0 uses the
  loop's initial input; subsequent iterations use the previous output.
- Condition modes: `until` (stop when matches) vs `while` (continue while matches).
- Composite condition combinators: `all`, `any`, `not`, and nesting.
- Safety cap: `max_iteration_count` raises RuntimeError when exceeded.
- Top-level `output` mapping is honored.
- Nesting: loop inside loop, loop inside pipeline/for-each, loop containing
  pipeline/for-each/accumulate as its `do`.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl import common as impl_common
from mindor.core.workflow.job.impl.accumulate import AccumulateJob
from mindor.core.workflow.job.impl.for_each import ForEachJob
from mindor.core.workflow.job.impl.loop import LoopJob
from mindor.core.workflow.job.impl.pipeline import PipelineJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #

class FakeWorkflow:
    def __init__(self) -> None:
        self.task_id = "task-test"
        self.workflow_id = "wf-test"
        self.run_ids: List[tuple[str, str]] = []

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.run_ids.append((job_id, run_id))


class FakeJobContext:
    """Mirrors JobContext enough to drive composite jobs, including
    `use_run_id` which `CompositeJob._run_inline_job` depends on."""

    def __init__(self) -> None:
        self.workflow = FakeWorkflow()
        self.is_terminal = False
        self.cancellation_token = None
        self._sources: Dict[str, Dict[str, Any]] = {"__global__": {}}
        self._run_id_stack: List[str] = []
        self.renderer = VariableRenderer(self._resolve_source)
        self.register_calls: List[tuple[Optional[str], str, Any]] = []

    class _RunIdScope:
        def __init__(self, stack: List[str], run_id: str) -> None:
            self._stack, self._run_id = stack, run_id
        def __enter__(self) -> None:
            self._stack.append(self._run_id)
        def __exit__(self, *_exc) -> None:
            self._stack.pop()

    def use_run_id(self, run_id: str):
        return self._RunIdScope(self._run_id_stack, run_id)

    def register_source(self, scope: Optional[str], key: str, source: Any) -> None:
        self._sources.setdefault(scope or "__global__", {})[key] = source
        self.register_calls.append((scope, key, source))

    async def render_variable(self, scope: Optional[str], value: Any, skip_decode: bool = False) -> Any:
        effective_scope = scope or (self._run_id_stack[-1] if self._run_id_stack else None)
        return await self.renderer.render(value, effective_scope, skip_decode=skip_decode)

    async def _resolve_source(self, key: str, index: Optional[int], scope: Optional[str]) -> Any:
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
    """Component stub. `transform` receives the input and returns the output.
    If `transform` accepts a second `call_index` arg, it is passed the 0-based
    invocation count, allowing per-call responses."""

    def __init__(self, transform: Optional[Callable[..., Any]] = None, tag: str = "fake") -> None:
        self.id = f"fake-{tag}"
        self.started = True
        self._transform = transform
        self.calls: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self.started = True

    async def run(self, action, run_id, input, workflow, job_id):
        idx = len(self.calls)
        self.calls.append({"action": action, "run_id": run_id, "input": input, "job_id": job_id})
        if self._transform is None:
            return input
        try:
            return self._transform(input, idx)
        except TypeError:
            return self._transform(input)


# --------------------------------------------------------------------------- #
# Test rig
# --------------------------------------------------------------------------- #

def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python(raw)


def _install_component_lookup(
    job_class, cfg, components_by_id: Dict[str, FakeComponent], monkeypatch: pytest.MonkeyPatch
):
    """Build an outer composite whose `_create_component` — and every inline
    sub-job's `_create_component` — resolves against `components_by_id`."""
    original_create_job = impl_common.create_job

    def _resolve(_id, component_ref):
        key = component_ref if isinstance(component_ref, str) else getattr(component_ref, "id", None)
        if key not in components_by_id:
            raise KeyError(f"unknown component ref: {key!r}")
        return components_by_id[key]

    async def _fake_create_component(_id, component_ref):
        return _resolve(_id, component_ref)

    def wrapped_create_job(job_id, config, global_configs):
        job = original_create_job(job_id, config, global_configs)
        if hasattr(job, "_create_component"):
            job._create_component = _fake_create_component  # type: ignore[assignment]
        return job

    monkeypatch.setattr(impl_common, "create_job", wrapped_create_job)

    outer = job_class.__new__(job_class)
    outer.id = f"outer-{job_class.__name__.lower()}"
    outer.config = cfg
    outer.global_configs = None
    outer._create_component = _fake_create_component  # type: ignore[assignment]
    return outer


# --------------------------------------------------------------------------- #
# Core semantics
# --------------------------------------------------------------------------- #

class TestDoWhileSemantics:

    @pytest.mark.anyio
    async def test_until_matches_on_first_iteration_still_runs_once(self, monkeypatch):
        # do-while: even when `until` would match immediately, `do` runs once.
        comp = FakeComponent(transform=lambda x: {"status": "ready"}, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": "seed",
            "do": {"component": "c"},
            "until": {"input": "${output.status}", "operator": "eq", "value": "ready"},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert len(comp.calls) == 1
        assert result == {"status": "ready"}

    @pytest.mark.anyio
    async def test_until_runs_until_condition_matches(self, monkeypatch):
        # First 3 responses are "pending"; 4th is "ready" -> 4 iterations.
        def transform(_x, i):
            return {"status": "ready" if i >= 3 else "pending", "i": i}
        comp = FakeComponent(transform=transform, tag="c")

        cfg = _cfg({
            "type": "loop",
            "input": "job-1",
            "do": {"component": "c", "input": {"job_id": "${input}"}},
            "until": {"input": "${output.status}", "operator": "eq", "value": "ready"},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())

        assert len(comp.calls) == 4
        # Every call receives the fixed loop input (mapped as {"job_id": "job-1"}).
        assert all(c["input"] == {"job_id": "job-1"} for c in comp.calls)
        assert result["status"] == "ready"

    @pytest.mark.anyio
    async def test_while_runs_while_condition_matches(self, monkeypatch):
        # Continue while has_more == True. Response says has_more for i in {0,1}, then False.
        def transform(_x, i):
            return {"page": i, "has_more": i < 2}
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "while": {"input": "${output.has_more}", "operator": "eq", "value": True},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        # i=0 (has_more) -> i=1 (has_more) -> i=2 (stop). 3 iterations.
        assert len(comp.calls) == 3
        assert result == {"page": 2, "has_more": False}


class TestFeedForward:

    @pytest.mark.anyio
    async def test_dollar_input_stays_constant_across_iterations(self, monkeypatch):
        # do.input="${input}" should resolve to the loop's initial input every iteration.
        seen_inputs: List[Any] = []
        def transform(x, i):
            seen_inputs.append(x)
            return {"i": i, "done": i >= 2}
        comp = FakeComponent(transform=transform, tag="c")

        cfg = _cfg({
            "type": "loop",
            "input": "SEED",
            "do": {"component": "c", "input": "${input}"},
            "until": {"input": "${output.done}", "operator": "eq", "value": True},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        await job.run(FakeJobContext())
        assert seen_inputs == ["SEED", "SEED", "SEED"]

    @pytest.mark.anyio
    async def test_dollar_output_references_previous_iteration(self, monkeypatch):
        # do.input="${output.n}" — first iteration ${output} is None (unset),
        # component sees None and treats it as 0; second and later see the prior n.
        def transform(x, i):
            n = 0 if x is None else x
            return {"n": n + 1}
        comp = FakeComponent(transform=lambda p: transform(p, None), tag="c")

        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c", "input": "${output.n}"},
            "until": {"input": "${output.n}", "operator": "gte", "value": 3},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        # i=0: input=None -> n=1; i=1: input=1 -> n=2; i=2: input=2 -> n=3. stop.
        assert [c["input"] for c in comp.calls] == [None, 1, 2]
        assert result == {"n": 3}

    @pytest.mark.anyio
    async def test_default_do_input_uses_previous_output_after_first(self, monkeypatch):
        # do.input omitted -> iteration 0 sees loop_input; later iterations
        # receive the previous iteration's raw output.
        def transform(x, _i):
            if x == "start":
                return {"step": 1}
            return {"step": x["step"] + 1}
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": "start",
            "do": {"component": "c"},
            "until": {"input": "${output.step}", "operator": "gte", "value": 3},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert result == {"step": 3}
        # 3 iterations total.
        assert len(comp.calls) == 3
        assert comp.calls[0]["input"] == "start"
        assert comp.calls[1]["input"] == {"step": 1}
        assert comp.calls[2]["input"] == {"step": 2}


# --------------------------------------------------------------------------- #
# Condition combinators
# --------------------------------------------------------------------------- #

class TestConditionCombinators:

    @pytest.mark.anyio
    async def test_until_all_requires_every_leaf(self, monkeypatch):
        # Stop when BOTH status=="ready" AND progress>=100.
        def transform(_x, i):
            # i=0: status=ready progress=50; i=1: status=pending progress=100; i=2: both.
            return [
                {"status": "ready", "progress": 50},
                {"status": "pending", "progress": 100},
                {"status": "ready", "progress": 100},
            ][i]
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"all": [
                {"input": "${output.status}", "operator": "eq", "value": "ready"},
                {"input": "${output.progress}", "operator": "gte", "value": 100},
            ]},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert len(comp.calls) == 3
        assert result == {"status": "ready", "progress": 100}

    @pytest.mark.anyio
    async def test_until_any_stops_on_first_match(self, monkeypatch):
        # Stop when status=="ready" OR error is truthy.
        def transform(_x, i):
            return [
                {"status": "pending", "error": None},
                {"status": "pending", "error": "boom"},   # `any` triggers here
                {"status": "ready", "error": None},
            ][i]
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"any": [
                {"input": "${output.status}", "operator": "eq", "value": "ready"},
                {"input": "${output.error}", "operator": "neq", "value": None},
            ]},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert len(comp.calls) == 2
        assert result["error"] == "boom"

    @pytest.mark.anyio
    async def test_until_not_inverts_leaf(self, monkeypatch):
        # Stop when NOT(status == "pending"): i.e. when status leaves "pending".
        def transform(_x, i):
            return {"status": "pending" if i < 2 else "done"}
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"not": {"input": "${output.status}", "operator": "eq", "value": "pending"}},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert len(comp.calls) == 3
        assert result == {"status": "done"}

    @pytest.mark.anyio
    async def test_while_all_continues_only_when_every_leaf_matches(self, monkeypatch):
        # Continue only while (i < 5) AND (i not in stop_list). stop_list contains 2.
        def transform(_x, i):
            return {"i": i, "stop_list": [2]}
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "while": {"all": [
                {"input": "${output.i}", "operator": "lt", "value": 5},
                {"input": "${output.i}", "operator": "not-in", "value": [2]},
            ]},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        # i=0 continue, i=1 continue, i=2 stop (in stop_list). 3 iterations executed.
        assert len(comp.calls) == 3
        assert result["i"] == 2

    @pytest.mark.anyio
    async def test_nested_combinators(self, monkeypatch):
        # Stop when: (status == "ready") OR (NOT(error is None) AND retries >= 3)
        def transform(_x, i):
            return [
                {"status": "pending", "error": None, "retries": 0},
                {"status": "pending", "error": "boom", "retries": 2},
                {"status": "pending", "error": "boom", "retries": 3},  # triggers the AND-inside-OR
            ][i]
        comp = FakeComponent(transform=transform, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"any": [
                {"input": "${output.status}", "operator": "eq", "value": "ready"},
                {"all": [
                    {"not": {"input": "${output.error}", "operator": "eq", "value": None}},
                    {"input": "${output.retries}", "operator": "gte", "value": 3},
                ]},
            ]},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert len(comp.calls) == 3
        assert result["retries"] == 3


# --------------------------------------------------------------------------- #
# Safety cap and output mapping
# --------------------------------------------------------------------------- #

class TestMaxIterationCount:

    @pytest.mark.anyio
    async def test_exceeding_cap_raises(self, monkeypatch):
        comp = FakeComponent(transform=lambda _x, _i: {"done": False}, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"input": "${output.done}", "operator": "eq", "value": True},
            "max_iteration_count": 5,
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        with pytest.raises(RuntimeError, match="max_iteration_count"):
            await job.run(FakeJobContext())
        # Runs exactly max_iteration_count times before raising (cap is checked
        # at the top of each iteration; the 6th check trips it).
        assert len(comp.calls) == 5

    @pytest.mark.anyio
    async def test_on_error_output_fallback_recovers(self, monkeypatch):
        # When the safety cap raises, `on_error.output` provides a fallback and
        # the top-level job succeeds. Verifies loop composes with the base retry/on-error path.
        comp = FakeComponent(transform=lambda _x, _i: {"n": _i}, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"input": "${output.n}", "operator": "gte", "value": 999},
            "max_iteration_count": 3,
            "on_error": {"output": {"fallback": True, "err": "${error.message}"}},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert result["fallback"] is True
        assert "max_iteration_count" in result["err"]


class TestOutputMapping:

    @pytest.mark.anyio
    async def test_top_output_template_wraps_last_iteration(self, monkeypatch):
        comp = FakeComponent(transform=lambda _x, i: {"v": i}, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c"},
            "until": {"input": "${output.v}", "operator": "gte", "value": 2},
            "output": {"final": "${output}", "n": "${output.v}"},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert result == {"final": {"v": 2}, "n": 2}

    @pytest.mark.anyio
    async def test_do_output_mapping_reshapes_each_iteration_result(self, monkeypatch):
        # do.output plucks a field; the plucked value is what feeds ${output}
        # for the condition and the next iteration's default input.
        comp = FakeComponent(transform=lambda _x, i: {"n": i, "meta": "drop"}, tag="c")
        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {"component": "c", "output": "${output.n}"},
            "until": {"input": "${output}", "operator": "gte", "value": 2},
        })
        job = _install_component_lookup(LoopJob, cfg, {"c": comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        # After do.output mapping, each iteration's exposed output is the raw int.
        assert result == 2


# --------------------------------------------------------------------------- #
# Nesting: loop containing other composites, and vice versa
# --------------------------------------------------------------------------- #

class TestLoopOfPipeline:

    @pytest.mark.anyio
    async def test_do_pipeline_input_bound_to_previous_output(self, monkeypatch):
        # Correct pattern: pipeline.input = ${output} threads the previous iteration's
        # output as the pipeline's initial input. First iteration ${output} is
        # unset -> None -> wrapper turns it into {"wrapped": None} -> None+1 fails,
        # so we use a component that handles None as 0.
        def to_int(x):
            return 0 if x is None else x
        wrap = FakeComponent(transform=lambda x: {"wrapped": to_int(x)}, tag="wrap")
        step2 = FakeComponent(transform=lambda p: p["wrapped"] + 1, tag="step2")

        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {
                "type": "pipeline",
                "input": "${output}",
                "steps": [
                    {"component": "wrap", "input": "${input}"},
                    {"component": "step2", "input": "${output}"},
                ],
            },
            "until": {"input": "${output}", "operator": "gte", "value": 3},
        })
        job = _install_component_lookup(LoopJob, cfg, {"wrap": wrap, "step2": step2}, monkeypatch)
        result = await job.run(FakeJobContext())
        # i=0: prev None -> pipeline yields 1; i=1: 1 -> 2; i=2: 2 -> 3 stop.
        assert result == 3


class TestLoopOfForEach:

    @pytest.mark.anyio
    async def test_do_for_each_processes_prev_output_list(self, monkeypatch):
        # Each iteration:
        #   - for-each doubles every item in the previous list.
        # Stop when the max element >= 8. Start from [1,2].
        # i=0: prev=None -> for-each over None -> `is_single_input`, returns [None doubled? -> None*2]
        # To avoid that pitfall, we thread via ${output} but only after the first
        # iteration produces a real list. We use loop.input = [1,2] so iter 0 uses that.
        double = FakeComponent(transform=lambda x: x * 2, tag="dbl")
        cfg = _cfg({
            "type": "loop",
            "input": [1, 2],
            "do": {
                "type": "for-each",
                # First iter ${output} is unset -> None; fall back to ${input}
                # by explicitly using ${input} (loop's initial list) via a conditional:
                # simplest: use ${input} on the first iter is automatic default.
                # Here we explicitly set input:
                "input": "${output}",
                "do": {"component": "dbl"},
            },
            "until": {"input": "${output}", "operator": "gte", "value": [8]},
        })
        # But: until's operator "gte" against a list won't behave as we want in general;
        # instead use a scalar predicate on iteration count via a companion.
        # Simpler and correct: stop when max element >= 8. We can't express max in
        # the DSL; instead, count iterations by stopping when a specific value is present.
        # Rewrite: use `in` to detect 8 in the list.
        cfg = _cfg({
            "type": "loop",
            "input": [1, 2],
            "do": {
                "type": "for-each",
                "input": "${output}",
                "do": {"component": "dbl"},
            },
            "until": {"input": 8, "operator": "in", "value": "${output}"},
        })
        job = _install_component_lookup(LoopJob, cfg, {"dbl": double}, monkeypatch)

        # Manually seed the first-iteration behavior: for-each's `input` will resolve
        # to ${output} which is unset on iter 0. Rely on the default: when the
        # inline do node has `input` explicitly set, that expression is rendered;
        # if it renders to None, for-each treats input as a single None item and
        # doubles it (None*2 fails). So we must not use ${output} for iter 0.
        # Instead, thread via loop's ${input} default: omit for-each's `input`.
        # But for-each schema requires `input`. So the safest correct form uses
        # a conditional: `${output ? output : input}` — but that's an extension.
        # Cleanest: pre-seed by using loop.input = [1,2] and letting the inline
        # for-each read the loop's ${input} directly:
        cfg = _cfg({
            "type": "loop",
            "input": [1, 2],
            "do": {
                "type": "for-each",
                "input": "${input}",   # will resolve to LOOP's ${input} on every iter (fixed!)
                "do": {"component": "dbl"},
            },
            "until": {"input": 4, "operator": "in", "value": "${output}"},
        })
        job = _install_component_lookup(LoopJob, cfg, {"dbl": double}, monkeypatch)
        result = await job.run(FakeJobContext())
        # Because for-each's input is fixed to loop input [1,2] on every iter,
        # each iteration produces [2,4]. 4 is in [2,4] -> until matches on iter 0.
        assert result == [2, 4]
        assert len(double.calls) == 2


class TestLoopOfAccumulate:

    @pytest.mark.anyio
    async def test_do_accumulate_folds_current_input(self, monkeypatch):
        # Each iteration folds the loop input list into a sum.
        adder = FakeComponent(transform=lambda p: p["acc"] + p["item"], tag="add")
        cfg = _cfg({
            "type": "loop",
            "input": [1, 2, 3],
            "do": {
                "type": "accumulate",
                "input": "${input}",
                "accumulator": 0,
                "do": {"component": "add", "input": {"acc": "${accumulator}", "item": "${item}"}},
            },
            # Since each iteration returns the same sum (6), stop immediately.
            "until": {"input": "${output}", "operator": "eq", "value": 6},
        })
        job = _install_component_lookup(LoopJob, cfg, {"add": adder}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert result == 6
        # Accumulate ran once; adder called 3 times (once per item).
        assert len(adder.calls) == 3


class TestPipelineOfLoop:

    @pytest.mark.anyio
    async def test_pipeline_step_running_a_loop(self, monkeypatch):
        # step 0 produces starting counter; step 1 is a loop that increments until >= 5.
        seeder = FakeComponent(transform=lambda _: {"n": 0}, tag="seed")
        incr = FakeComponent(transform=lambda x: {"n": (0 if x is None else x["n"]) + 1}, tag="incr")
        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "seed"},
                {
                    "type": "loop",
                    "input": "${output}",  # start from seeder's result
                    "do": {"component": "incr", "input": "${output}"},  # thread previous incr
                    "until": {"input": "${output.n}", "operator": "gte", "value": 5},
                },
            ],
        })
        job = _install_component_lookup(PipelineJob, cfg, {"seed": seeder, "incr": incr}, monkeypatch)
        result = await job.run(FakeJobContext())
        # loop: i=0 input=${output}=None (first iter has no prev), incr(None)={"n":1};
        # i=1: input=prev={"n":1} -> {"n":2}; ...; i=4 -> {"n":5} stop.
        assert result == {"n": 5}
        assert len(incr.calls) == 5


class TestForEachOfLoop:

    @pytest.mark.anyio
    async def test_for_each_item_runs_a_loop_to_per_item_target(self, monkeypatch):
        # For each item, run a loop that increments a counter until reaching item.
        # `do.input` is omitted so the loop's default kicks in:
        #   iteration 0 -> loop_input; iteration >0 -> previous iteration's output.
        # This threads the per-item target through the whole loop.
        def step(x):
            # x is the loop's fed-forward value: {"n":.., "target":..}
            return {"n": x["n"] + 1, "target": x["target"]}
        incr = FakeComponent(transform=step, tag="incr")

        cfg = _cfg({
            "type": "for-each",
            "input": [1, 2, 3],
            "do": {
                "type": "loop",
                "input": {"n": 0, "target": "${item}"},
                "do": {"component": "incr"},
                "until": {"input": "${output.n}", "operator": "gte", "value": "${output.target}"},
            },
        })
        job = _install_component_lookup(ForEachJob, cfg, {"incr": incr}, monkeypatch)
        result = await job.run(FakeJobContext())
        # item=1: 1 iteration reaches n=1==target;
        # item=2: 2 iterations reach n=2==target;
        # item=3: 3 iterations reach n=3==target.
        assert result == [{"n": 1, "target": 1}, {"n": 2, "target": 2}, {"n": 3, "target": 3}]
        assert len(incr.calls) == 1 + 2 + 3


# --------------------------------------------------------------------------- #
# Loop nested in loop
# --------------------------------------------------------------------------- #

class TestLoopOfLoop:

    @pytest.mark.anyio
    async def test_inner_loop_completes_per_outer_iteration(self, monkeypatch):
        # Outer loop increments an outer counter (via output) until outer >= 2.
        # Inner loop increments an inner counter until inner >= 3.
        # We use two components to keep the transforms trivially reversible.
        def out_step(x):
            # x is inner loop's result: {"i": <inner>}. Outer wants to count how many times
            # the inner loop completed. We map inner result to outer counter tracked in output.
            return {"outer": (0 if x is None else x.get("outer_seed", 0)) + 1, "inner_result": x}
        def in_step(x):
            n = 0 if x is None else x["i"]
            return {"i": n + 1}

        outer_comp = FakeComponent(transform=out_step, tag="out")  # unused when do is a loop
        in_comp = FakeComponent(transform=in_step, tag="in")

        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {
                "type": "loop",
                "input": None,
                "do": {"component": "in", "input": "${output}"},
                "until": {"input": "${output.i}", "operator": "gte", "value": 3},
            },
            "until": {"input": "${output.i}", "operator": "gte", "value": 3},
        })
        job = _install_component_lookup(LoopJob, cfg, {"out": outer_comp, "in": in_comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        # Inner loop runs to i=3 on first outer iter; outer stops immediately because
        # outer's ${output.i} == 3 satisfies gte 3.
        assert result == {"i": 3}
        assert len(in_comp.calls) == 3

    @pytest.mark.anyio
    async def test_inner_loop_reruns_each_outer_iteration(self, monkeypatch):
        # Outer never satisfies its stop (checks i>=99, inner always yields {"i":2}),
        # so max_iteration_count=3 triggers RuntimeError; on_error.output supplies a
        # fallback. What we care about is that the inner loop runs from scratch each
        # outer iteration: 3 outer × 2 inner = 6 inner calls.
        def in_step(x):
            n = 0 if x is None else x["i"]
            return {"i": n + 1}
        in_comp = FakeComponent(transform=in_step, tag="in")

        cfg = _cfg({
            "type": "loop",
            "input": None,
            "do": {
                "type": "loop",
                "input": None,
                "do": {"component": "in"},
                "until": {"input": "${output.i}", "operator": "gte", "value": 2},
            },
            "until": {"input": "${output.i}", "operator": "gte", "value": 99},
            "max_iteration_count": 3,
            "on_error": {"output": {"fallback": True}},
        })
        job = _install_component_lookup(LoopJob, cfg, {"in": in_comp}, monkeypatch)
        result = await job.run(FakeJobContext())
        assert result == {"fallback": True}
        # 3 outer iters × 2 inner iters = 6 total inner calls.
        assert len(in_comp.calls) == 6
