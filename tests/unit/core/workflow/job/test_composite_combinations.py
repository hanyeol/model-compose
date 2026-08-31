"""Combination tests for PipelineJob / ForEachJob / AccumulateJob.

Each composite job supports an inline `do` (for-each, accumulate) or
`steps` (pipeline) that can itself be another composite job. Individual
composites are covered in their own files; this suite exercises the
cross-composite nesting paths where bugs in scoping, output propagation,
and per-iteration `_create_component` are most likely to hide.

Component construction is stubbed at both the outer and inner layers by
wrapping `create_job` so every job produced during a run has its
`_create_component` replaced with a lookup into a shared component map.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest
from pydantic import TypeAdapter

from mindor.core.foundation.variable.renderer import VariableRenderer
from mindor.core.workflow.job.impl import common as impl_common
from mindor.core.workflow.job.impl.accumulate import AccumulateJob
from mindor.core.workflow.job.impl.for_each import ForEachJob
from mindor.core.workflow.job.impl.pipeline import PipelineJob
from mindor.dsl.schema.job import JobConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --------------------------------------------------------------------------- #
# Fakes: workflow, job context, component
# --------------------------------------------------------------------------- #

class FakeWorkflow:
    def __init__(self) -> None:
        self.task_id = "task-test"
        self.workflow_id = "wf-test"
        self.run_ids: List[tuple[str, str]] = []

    def record_run_id(self, job_id: str, run_id: str) -> None:
        self.run_ids.append((job_id, run_id))


class FakeJobContext:
    """Mirrors `mindor.core.workflow.job.context.JobContext` closely enough
    to drive composite jobs — including the `use_run_id` stack that
    `CompositeJob._run_inline_job` depends on."""

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
            self._stack = stack
            self._run_id = run_id

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
        # Fall back to the global scope so nested composites can resolve
        # outer-scope names (e.g., pipeline step reading pipeline `${input}`).
        outer = self._sources.get("__global__", {})
        if key in outer:
            value = outer[key]
            return value[index] if index is not None and isinstance(value, list) else value
        return None


class FakeComponent:
    """Configurable stand-in for a ComponentService."""

    def __init__(self, transform=None, tag: str = "fake") -> None:
        self.id = f"fake-{tag}"
        self.started = True
        self._transform = transform
        self.calls: List[Dict[str, Any]] = []

    async def start(self) -> None:
        self.started = True

    async def run(self, action, run_id, input, workflow, job_id):
        self.calls.append(
            {"action": action, "run_id": run_id, "input": input, "job_id": job_id}
        )
        return self._transform(input) if self._transform else input


# --------------------------------------------------------------------------- #
# Test rig: build a composite job whose _create_component (at every nesting
# level) resolves from a shared { component_id: FakeComponent } map.
# --------------------------------------------------------------------------- #

def _cfg(raw: dict):
    return TypeAdapter(JobConfig).validate_python(raw)


def _install_component_lookup(
    job_cls, cfg, components_by_id: Dict[str, FakeComponent], monkeypatch: pytest.MonkeyPatch
):
    """Build an outer composite job whose `_create_component` — and that of
    every inline sub-job created via `create_job` at runtime — is stubbed
    to return the FakeComponent whose id matches the requested reference."""
    original_create_job = impl_common.create_job

    def _resolve(_id, component_ref):
        # `component_ref` is either a component id string (external reference)
        # or an inline ComponentConfig object with an `id` attribute.
        key = component_ref if isinstance(component_ref, str) else getattr(component_ref, "id", None)
        if key not in components_by_id:
            raise KeyError(f"unknown component ref: {key!r}")
        return components_by_id[key]

    async def _fake_create_component(_id, component_ref):
        return _resolve(_id, component_ref)

    def wrapped_create_job(job_id, config, global_configs):
        job = original_create_job(job_id, config, global_configs)
        # Only ComponentRunnerJob subclasses expose _create_component.
        if hasattr(job, "_create_component"):
            job._create_component = _fake_create_component  # type: ignore[assignment]
        return job

    monkeypatch.setattr(impl_common, "create_job", wrapped_create_job)

    outer = job_cls.__new__(job_cls)
    outer.id = f"outer-{job_cls.__name__.lower()}"
    outer.config = cfg
    outer.global_configs = None
    outer._create_component = _fake_create_component  # type: ignore[assignment]
    return outer


# --------------------------------------------------------------------------- #
# Pipeline containing a for-each step
# --------------------------------------------------------------------------- #

class TestPipelineOfForEach:
    @pytest.mark.anyio
    async def test_for_each_step_receives_previous_output_as_input_source(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # step 0 (component) turns "hi" into [1,2,3];
        # step 1 (for-each over ${output}) doubles each item.
        producer = FakeComponent(transform=lambda _: [1, 2, 3], tag="producer")
        doubler = FakeComponent(transform=lambda x: x * 2, tag="doubler")

        cfg = _cfg({
            "type": "pipeline",
            "input": "hi",
            "steps": [
                {"component": "producer", "action": "a", "input": "${input}"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {"component": "doubler", "action": "a"},
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob, cfg, {"producer": producer, "doubler": doubler}, monkeypatch
        )

        result = await job.run(FakeJobContext())

        assert result == [2, 4, 6]
        assert [c["input"] for c in doubler.calls] == [1, 2, 3]

    @pytest.mark.anyio
    async def test_for_each_step_output_template_wraps_each_item(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        producer = FakeComponent(transform=lambda _: ["a", "b"], tag="producer")
        echo = FakeComponent(tag="echo")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {
                        "component": "echo",
                        "action": "a",
                        "output": {"wrapped": "${output}"},
                    },
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob, cfg, {"producer": producer, "echo": echo}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == [{"wrapped": "a"}, {"wrapped": "b"}]


# --------------------------------------------------------------------------- #
# Pipeline containing an accumulate step
# --------------------------------------------------------------------------- #

class TestPipelineOfAccumulate:
    @pytest.mark.anyio
    async def test_accumulate_step_folds_previous_output(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        producer = FakeComponent(transform=lambda _: [1, 2, 3, 4], tag="producer")
        # `adder` receives {"acc": ..., "item": ...} and returns their sum.
        # The do.input template supplies both from the accumulate frame.
        adder = FakeComponent(transform=lambda p: p["acc"] + p["item"], tag="adder")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "accumulate",
                    "input": "${output}",
                    "accumulator": 0,
                    "do": {
                        "component": "adder",
                        "action": "a",
                        "input": {"acc": "${accumulator}", "item": "${item}"},
                    },
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob, cfg, {"producer": producer, "adder": adder}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == 10  # 0+1+2+3+4


# --------------------------------------------------------------------------- #
# ForEach whose `do` is itself a pipeline
# --------------------------------------------------------------------------- #

class TestForEachOfPipeline:
    @pytest.mark.anyio
    async def test_per_item_pipeline_threads_item_through_steps(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # For each item x, pipeline: x -> x+1 -> (x+1)*10.
        c1 = FakeComponent(transform=lambda x: x + 1, tag="c1")
        c2 = FakeComponent(transform=lambda x: x * 10, tag="c2")

        cfg = _cfg({
            "type": "for-each",
            "input": [1, 2, 3],
            "do": {
                "type": "pipeline",
                "input": "${item}",
                "steps": [
                    {"component": "c1", "action": "a", "input": "${input}"},
                    {"component": "c2", "action": "a", "input": "${output}"},
                ],
            },
        })
        job = _install_component_lookup(ForEachJob, cfg, {"c1": c1, "c2": c2}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == [20, 30, 40]
        # Both components should have been invoked once per item.
        assert len(c1.calls) == 3
        assert len(c2.calls) == 3

    @pytest.mark.anyio
    async def test_per_item_pipeline_with_output_mapping_on_inner_step(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Inner step[0] output template extracts `.value` before feeding step[1].
        producer = FakeComponent(transform=lambda x: {"value": x, "meta": "drop"}, tag="producer")
        consumer = FakeComponent(transform=lambda x: f"got:{x}", tag="consumer")

        cfg = _cfg({
            "type": "for-each",
            "input": ["a", "b"],
            "do": {
                "type": "pipeline",
                "input": "${item}",
                "steps": [
                    {
                        "component": "producer",
                        "action": "a",
                        "input": "${input}",
                        "output": "${output.value}",
                    },
                    {"component": "consumer", "action": "a", "input": "${output}"},
                ],
            },
        })
        job = _install_component_lookup(
            ForEachJob, cfg, {"producer": producer, "consumer": consumer}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == ["got:a", "got:b"]


# --------------------------------------------------------------------------- #
# ForEach whose `do` is an accumulate
# --------------------------------------------------------------------------- #

class TestForEachOfAccumulate:
    @pytest.mark.anyio
    async def test_each_item_is_folded_into_its_own_accumulator(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Outer for-each iterates over [ [1,2,3], [10,20] ]. Each inner
        # accumulate folds its list into a sum starting from 0.
        adder = FakeComponent(transform=lambda p: p["acc"] + p["item"], tag="adder")

        cfg = _cfg({
            "type": "for-each",
            "input": [[1, 2, 3], [10, 20]],
            "do": {
                "type": "accumulate",
                "input": "${item}",
                "accumulator": 0,
                "do": {
                    "component": "adder",
                    "action": "a",
                    "input": {"acc": "${accumulator}", "item": "${item}"},
                },
            },
        })
        job = _install_component_lookup(ForEachJob, cfg, {"adder": adder}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == [6, 30]


# --------------------------------------------------------------------------- #
# Accumulate whose `do` is itself a pipeline
# --------------------------------------------------------------------------- #

class TestAccumulateOfPipeline:
    @pytest.mark.anyio
    async def test_pipeline_as_do_replaces_accumulator_each_iteration(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # A pipeline whose steps don't reference `${accumulator}` simply
        # replaces the accumulator with its own final step output each pass —
        # useful as a plain "map-and-forget" pattern where accumulate is
        # essentially reduced to `last iteration wins`.
        doubler = FakeComponent(transform=lambda x: x * 2, tag="doubler")
        stringify = FakeComponent(transform=lambda x: f"n={x}", tag="stringify")

        cfg = _cfg({
            "type": "accumulate",
            "input": [1, 2, 3],
            "accumulator": "initial",
            "do": {
                "type": "pipeline",
                "input": "${item}",
                "steps": [
                    {"component": "doubler", "action": "a", "input": "${input}"},
                    {"component": "stringify", "action": "a", "input": "${output}"},
                ],
            },
        })
        job = _install_component_lookup(
            AccumulateJob, cfg, {"doubler": doubler, "stringify": stringify}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == "n=6"  # final: 3 -> 6 -> "n=6"
        assert len(doubler.calls) == 3
        assert len(stringify.calls) == 3


# --------------------------------------------------------------------------- #
# Accumulate whose `do` is a for-each
# --------------------------------------------------------------------------- #

class TestAccumulateOfForEach:
    @pytest.mark.anyio
    async def test_inner_for_each_output_replaces_accumulator(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Iterate lists [[1,2],[3,4]]. For each list, the inner for-each
        # doubles every entry and the whole doubled list is emitted as
        # the new accumulator (accumulator not folded — replaced).
        doubler = FakeComponent(transform=lambda x: x * 2, tag="doubler")

        cfg = _cfg({
            "type": "accumulate",
            "input": [[1, 2], [3, 4]],
            "accumulator": None,
            "do": {
                "type": "for-each",
                "input": "${item}",
                "do": {"component": "doubler", "action": "a"},
            },
        })
        job = _install_component_lookup(AccumulateJob, cfg, {"doubler": doubler}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == [6, 8]  # final iteration wins


# --------------------------------------------------------------------------- #
# Three-level nesting
# --------------------------------------------------------------------------- #

class TestThreeLevelNesting:
    @pytest.mark.anyio
    async def test_pipeline_of_for_each_of_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Pipeline:
        #   step 0: producer -> [ [1,2], [3,4] ]
        #   step 1: for-each over ${output}; for each sublist,
        #           run a pipeline (sum then negate).
        producer = FakeComponent(transform=lambda _: [[1, 2], [3, 4]], tag="producer")
        summer = FakeComponent(transform=lambda xs: sum(xs), tag="summer")
        negator = FakeComponent(transform=lambda x: -x, tag="negator")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {
                        "type": "pipeline",
                        "input": "${item}",
                        "steps": [
                            {"component": "summer", "action": "a", "input": "${input}"},
                            {"component": "negator", "action": "a", "input": "${output}"},
                        ],
                    },
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob,
            cfg,
            {"producer": producer, "summer": summer, "negator": negator},
            monkeypatch,
        )

        result = await job.run(FakeJobContext())
        assert result == [-3, -7]

    @pytest.mark.anyio
    async def test_for_each_of_accumulate_of_component_folds_per_group(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # 3-level composition where the innermost body is a plain component
        # (not a pipeline) so `${accumulator}` renders in the accumulate frame
        # exactly like the single-level accumulate case. This exercises the
        # for-each -> accumulate transition without hitting the pipeline
        # step-scope isolation.
        adder = FakeComponent(transform=lambda p: p["acc"] + p["item"], tag="adder")

        cfg = _cfg({
            "type": "for-each",
            "input": [[1, 2, 3], [4, 5]],
            "do": {
                "type": "accumulate",
                "input": "${item}",
                "accumulator": 0,
                "do": {
                    "component": "adder",
                    "action": "a",
                    "input": {"acc": "${accumulator}", "item": "${item}"},
                },
            },
        })
        job = _install_component_lookup(ForEachJob, cfg, {"adder": adder}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == [6, 9]  # sum([1,2,3])=6, sum([4,5])=9


# --------------------------------------------------------------------------- #
# Pipeline mixing every step kind
# --------------------------------------------------------------------------- #

class TestPipelineMixedSteps:
    @pytest.mark.anyio
    async def test_component_then_for_each_then_accumulate(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        producer = FakeComponent(transform=lambda _: [1, 2, 3], tag="producer")
        squarer = FakeComponent(transform=lambda x: x * x, tag="squarer")
        adder = FakeComponent(transform=lambda p: p["acc"] + p["item"], tag="adder")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {"component": "squarer", "action": "a"},
                },
                {
                    "type": "accumulate",
                    "input": "${output}",
                    "accumulator": 0,
                    "do": {
                        "component": "adder",
                        "action": "a",
                        "input": {"acc": "${accumulator}", "item": "${item}"},
                    },
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob,
            cfg,
            {"producer": producer, "squarer": squarer, "adder": adder},
            monkeypatch,
        )

        result = await job.run(FakeJobContext())
        # 1 + 4 + 9
        assert result == 14


# --------------------------------------------------------------------------- #
# Scoping: nested `${input}` / `${output}` must resolve to the *nearest*
# enclosing composite's frame, not leak across boundaries.
# --------------------------------------------------------------------------- #

class TestScopingBoundaries:
    @pytest.mark.anyio
    async def test_inner_pipeline_input_shadows_outer_pipeline_input(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Outer pipeline input = "outer". A for-each step iterates ["x","y"].
        # The inner pipeline input is bound to ${item} — its steps' ${input}
        # must resolve to the item, not "outer".
        upper = FakeComponent(transform=lambda x: x.upper() if isinstance(x, str) else x, tag="upper")

        cfg = _cfg({
            "type": "pipeline",
            "input": "outer",
            "steps": [
                {
                    "type": "for-each",
                    "input": ["x", "y"],
                    "do": {
                        "type": "pipeline",
                        "input": "${item}",
                        "steps": [
                            {"component": "upper", "action": "a", "input": "${input}"},
                        ],
                    },
                },
            ],
        })
        job = _install_component_lookup(PipelineJob, cfg, {"upper": upper}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == ["X", "Y"]
        assert [c["input"] for c in upper.calls] == ["x", "y"]


# --------------------------------------------------------------------------- #
# Edge cases
# --------------------------------------------------------------------------- #

class TestNestedEdgeCases:
    @pytest.mark.anyio
    async def test_for_each_step_over_empty_list_yields_empty_and_pipeline_still_completes(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        producer = FakeComponent(transform=lambda _: [], tag="producer")
        never_called = FakeComponent(transform=lambda x: x, tag="never")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {"component": "never", "action": "a"},
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob, cfg, {"producer": producer, "never": never_called}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == []
        assert never_called.calls == []

    @pytest.mark.anyio
    async def test_accumulate_over_single_element_still_runs_do_once(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Single-element input still triggers exactly one `do` invocation.
        adder = FakeComponent(transform=lambda p: p["acc"] + p["value"], tag="adder")

        cfg = _cfg({
            "type": "accumulate",
            "input": [42],
            "accumulator": 8,
            "do": {
                "component": "adder",
                "action": "a",
                "input": {"acc": "${accumulator}", "value": "${item}"},
            },
        })
        job = _install_component_lookup(AccumulateJob, cfg, {"adder": adder}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == 50
        assert len(adder.calls) == 1

    @pytest.mark.anyio
    async def test_for_each_batch_size_still_processes_all_items_in_nested_pipeline(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # batch_size > 1 changes concurrency but must preserve order and
        # completeness of the collected results.
        doubler = FakeComponent(transform=lambda x: x * 2, tag="doubler")
        incrementer = FakeComponent(transform=lambda x: x + 1, tag="incr")

        cfg = _cfg({
            "type": "for-each",
            "input": [1, 2, 3, 4, 5],
            "batch_size": 2,
            "do": {
                "type": "pipeline",
                "input": "${item}",
                "steps": [
                    {"component": "doubler", "action": "a", "input": "${input}"},
                    {"component": "incr", "action": "a", "input": "${output}"},
                ],
            },
        })
        job = _install_component_lookup(
            ForEachJob, cfg, {"doubler": doubler, "incr": incrementer}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == [3, 5, 7, 9, 11]

    @pytest.mark.anyio
    async def test_accumulate_starting_with_list_accumulator_can_append_via_spread(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Fold items into a list-shaped accumulator. `do.output` renders under
        # the accumulate frame — so both `...${accumulator}` and `${item}`
        # resolve, and the list grows each iteration.
        identity = FakeComponent(tag="identity")

        cfg = _cfg({
            "type": "accumulate",
            "input": ["a", "b", "c"],
            "accumulator": [],
            "do": {
                "component": "identity",
                "action": "a",
                "output": ["...${accumulator}", "${item}"],
            },
        })
        job = _install_component_lookup(AccumulateJob, cfg, {"identity": identity}, monkeypatch)

        result = await job.run(FakeJobContext())
        assert result == ["a", "b", "c"]

    @pytest.mark.anyio
    async def test_top_level_output_template_around_nested_composite_result(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        # Outer pipeline wraps the nested for-each output into a dict.
        producer = FakeComponent(transform=lambda _: ["x", "y"], tag="producer")
        upper = FakeComponent(transform=lambda x: x.upper(), tag="upper")

        cfg = _cfg({
            "type": "pipeline",
            "input": None,
            "output": {"items": "${output}", "first": "${output[0]}"},
            "steps": [
                {"component": "producer", "action": "a"},
                {
                    "type": "for-each",
                    "input": "${output}",
                    "do": {"component": "upper", "action": "a"},
                },
            ],
        })
        job = _install_component_lookup(
            PipelineJob, cfg, {"producer": producer, "upper": upper}, monkeypatch
        )

        result = await job.run(FakeJobContext())
        assert result == {"items": ["X", "Y"], "first": "X"}
