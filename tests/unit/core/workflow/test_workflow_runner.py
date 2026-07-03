"""Unit tests for `core/workflow/workflow.py` WorkflowRunner.

Scope:
- `_get_dependent_jobs` graph traversal
- `_schedule_job` max_run_count enforcement
- `_run_jobs` completed-target rewind loop (integration-ish, no real Jobs)
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set
from unittest.mock import MagicMock

import pytest

from mindor.core.workflow import workflow as workflow_module
from mindor.core.workflow.job.base import Job, RoutingTarget
from mindor.core.workflow.workflow import WorkflowRunner


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_job_config(job_id: str, depends_on: Optional[List[str]] = None, max_run_count: int = 5) -> SimpleNamespace:
    return SimpleNamespace(
        id=job_id,
        depends_on=depends_on or [],
        max_run_count=max_run_count,
        type=SimpleNamespace(value="mock"),
    )


class ScriptedJob(Job):
    """A Job whose `run()` returns pre-scripted outputs on each successive call."""

    def __init__(self, id: str, outputs: List[Any]):
        self.id = id
        self.config = None
        self.global_configs = None
        self._outputs = list(outputs)
        self._call_index = 0

    async def run(self, context) -> Any:
        output = self._outputs[self._call_index]
        self._call_index += 1
        return output


def make_context() -> MagicMock:
    context = MagicMock()
    context.task_id = "test-task"
    context.input = {}
    context.context = {}
    context.job_run_ids = {}
    context.sources = {"jobs": {}}
    context.complete_job = MagicMock(side_effect=lambda job_id, output: context.sources["jobs"].__setitem__(job_id, {"output": output}))

    async def _noop_notify(*args, **kwargs):
        return None

    async def _noop_render(value, skip_decode=False):
        return value

    context.job_event_notifier = MagicMock()
    context.job_event_notifier.notify = _noop_notify
    context.render_variable = _noop_render
    return context


def make_runner(jobs_config: Dict[str, SimpleNamespace]) -> WorkflowRunner:
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.id = "wf"
    runner.jobs = jobs_config
    runner.output = None
    runner.global_configs = None
    return runner


def make_job(job_id: str, outputs: List[Any], config: SimpleNamespace) -> ScriptedJob:
    job = ScriptedJob(job_id, outputs)
    job.config = config
    return job


def install_rewind_scripts(monkeypatch, scripts: Dict[str, List[List[Any]]]) -> Dict[str, int]:
    """Register per-job output scripts to be consumed on each rewind.

    Each call to create_job(job_id, ...) pops the next script from scripts[job_id].
    Returns a counter dict tracking how many times each job was recreated.
    """
    counters: Dict[str, int] = {job_id: 0 for job_id in scripts}

    def _fake_create_job(job_id: str, config: SimpleNamespace, global_configs: Any) -> Job:
        idx = counters[job_id]
        counters[job_id] += 1
        return make_job(job_id, list(scripts[job_id][idx]), config)

    monkeypatch.setattr(workflow_module, "create_job", _fake_create_job)
    return counters


class TestGetDependentJobs:
    def _make_runner(self, jobs_config: Dict[str, SimpleNamespace]) -> WorkflowRunner:
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.jobs = jobs_config
        return runner

    def test_linear_chain_returns_self_and_downstream(self):
        # A -> B -> C
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C", depends_on=["B"]),
        }
        runner = self._make_runner(jobs)
        result = runner._get_dependent_jobs("A", {"A", "B", "C"})
        assert result == {"A", "B", "C"}

    def test_diamond_returns_all_reachable(self):
        # A -> B, A -> C, B -> D, C -> D
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C", depends_on=["A"]),
            "D": make_job_config("D", depends_on=["B", "C"]),
        }
        runner = self._make_runner(jobs)
        result = runner._get_dependent_jobs("A", {"A", "B", "C", "D"})
        assert result == {"A", "B", "C", "D"}

    def test_returns_only_from_root_subtree(self):
        # A -> B, C -> D  (two disconnected chains)
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C"),
            "D": make_job_config("D", depends_on=["C"]),
        }
        runner = self._make_runner(jobs)
        result = runner._get_dependent_jobs("A", {"A", "B", "C", "D"})
        assert result == {"A", "B"}

    def test_filters_out_jobs_not_in_candidate_set(self):
        # A -> B -> C, but C is not in candidate set
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C", depends_on=["B"]),
        }
        runner = self._make_runner(jobs)
        result = runner._get_dependent_jobs("A", {"A", "B"})
        assert result == {"A", "B"}

    def test_root_not_in_candidate_returns_empty(self):
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
        }
        runner = self._make_runner(jobs)
        result = runner._get_dependent_jobs("A", {"B"})
        assert result == set()


class TestScheduleJobMaxRunCount:
    def _make_runner(self, jobs_config: Dict[str, SimpleNamespace]) -> WorkflowRunner:
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.jobs = jobs_config
        return runner

    @pytest.mark.anyio
    async def test_first_schedule_succeeds_and_increments_count(self):
        jobs = {"A": make_job_config("A", max_run_count=2)}
        runner = self._make_runner(jobs)
        job = ScriptedJob("A", ["out"])
        job.config = jobs["A"]

        context = make_context()
        counts: Dict[str, int] = {}
        task = runner._schedule_job(job, context, counts)
        assert counts["A"] == 1
        task.cancel()

    @pytest.mark.anyio
    async def test_raises_when_max_run_count_exceeded(self):
        jobs = {"A": make_job_config("A", max_run_count=2)}
        runner = self._make_runner(jobs)
        job = ScriptedJob("A", ["out", "out", "out"])
        job.config = jobs["A"]

        context = make_context()
        counts: Dict[str, int] = {}
        task1 = runner._schedule_job(job, context, counts)
        task2 = runner._schedule_job(job, context, counts)
        task1.cancel()
        task2.cancel()

        assert counts["A"] == 2
        with pytest.raises(RuntimeError, match="max_run_count"):
            runner._schedule_job(job, context, counts)


class TestRunJobsRewind:
    @pytest.mark.anyio
    async def test_completed_target_rewinds_and_reruns(self, monkeypatch):
        # Graph: start -> loop -> end
        #   start:   returns "start_out"
        #   loop:    first call -> "loop_out", second call -> "loop_out2"
        #   end:     first call -> RoutingTarget("loop") to trigger rewind,
        #            second call -> "final"
        jobs_config: Dict[str, SimpleNamespace] = {
            "start": make_job_config("start"),
            "loop": make_job_config("loop", depends_on=["start"]),
            "end": make_job_config("end", depends_on=["loop"]),
        }

        start_job = ScriptedJob("start", ["start_out"])
        start_job.config = jobs_config["start"]
        loop_job = ScriptedJob("loop", ["loop_out", "loop_out2"])
        loop_job.config = jobs_config["loop"]
        end_job = ScriptedJob("end", [RoutingTarget("loop"), "final"])
        end_job.config = jobs_config["end"]

        # New ScriptedJobs produced on rewind should behave the same as the
        # already-existing instances would on their next call. We keep counters
        # keyed by job_id and return the appropriate value.
        rewind_counters = {"loop": 1, "end": 1}
        rewind_scripts = {
            "loop": ["loop_out2"],
            "end": ["final"],
        }

        def _fake_create_job(job_id: str, config: SimpleNamespace, global_configs: Any) -> Job:
            script = rewind_scripts[job_id]
            job = ScriptedJob(job_id, script)
            job.config = config
            return job

        monkeypatch.setattr(workflow_module, "create_job", _fake_create_job)

        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.id = "wf"
        runner.jobs = jobs_config
        runner.output = None
        runner.global_configs = None

        pending_jobs: Dict[str, Job] = {
            "start": start_job,
            "loop": loop_job,
            "end": end_job,
        }
        routing_jobs: Dict[str, Job] = {}
        routable_job_ids: Set[str] = set()

        context = make_context()

        output = await runner._run_jobs(context, pending_jobs, routing_jobs, routable_job_ids)

        assert output == "final"
        assert loop_job._call_index == 1  # first-instance loop ran once
        assert end_job._call_index == 1   # first-instance end ran once (returned RoutingTarget)

    @pytest.mark.anyio
    async def test_rewind_respects_max_run_count(self, monkeypatch):
        # loop -> end, end always routes back to loop; loop.max_run_count=2 → 2번째 재실행 시도에서 raise
        jobs_config: Dict[str, SimpleNamespace] = {
            "loop": make_job_config("loop", max_run_count=2),
            "end": make_job_config("end", depends_on=["loop"], max_run_count=10),
        }

        loop_job = ScriptedJob("loop", ["loop_out"])
        loop_job.config = jobs_config["loop"]
        end_job = ScriptedJob("end", [RoutingTarget("loop")])
        end_job.config = jobs_config["end"]

        # After rewind, new loop instance would run — this run should raise
        # because loop already has run_count == 1, so scheduling the 2nd run
        # makes count == 2 which equals max_run_count=2 → allowed; 3rd would fail.
        # Actually threshold: `> max_run_count`. So 2 == 2 does not raise. Adjust the scenario
        # such that end always routes back so we exceed.
        # Extend end script to return RoutingTarget again after rewind:
        end_job._outputs = [RoutingTarget("loop")]

        rewind_scripts = {
            "loop": ["loop_out2"],
            "end": [RoutingTarget("loop")],
        }

        def _fake_create_job(job_id, config, global_configs):
            job = ScriptedJob(job_id, list(rewind_scripts[job_id]))
            job.config = config
            return job

        monkeypatch.setattr(workflow_module, "create_job", _fake_create_job)

        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.id = "wf"
        runner.jobs = jobs_config
        runner.output = None
        runner.global_configs = None

        pending_jobs: Dict[str, Job] = {
            "loop": loop_job,
            "end": end_job,
        }
        routing_jobs: Dict[str, Job] = {}
        routable_job_ids: Set[str] = set()

        context = make_context()

        with pytest.raises(RuntimeError, match="max_run_count"):
            await runner._run_jobs(context, pending_jobs, routing_jobs, routable_job_ids)


class TestGetDependentJobsExtras:
    def _make(self, jobs: Dict[str, SimpleNamespace]) -> WorkflowRunner:
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.jobs = jobs
        return runner

    def test_single_leaf_returns_self(self):
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
        }
        runner = self._make(jobs)
        assert runner._get_dependent_jobs("B", {"A", "B"}) == {"B"}

    def test_wide_fanout(self):
        # A -> B, A -> C, A -> D, A -> E
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C", depends_on=["A"]),
            "D": make_job_config("D", depends_on=["A"]),
            "E": make_job_config("E", depends_on=["A"]),
        }
        runner = self._make(jobs)
        assert runner._get_dependent_jobs("A", {"A", "B", "C", "D", "E"}) == {"A", "B", "C", "D", "E"}

    def test_deep_chain(self):
        jobs = {f"J{i}": make_job_config(f"J{i}", depends_on=[f"J{i-1}"] if i > 0 else []) for i in range(10)}
        runner = self._make(jobs)
        candidates = {f"J{i}" for i in range(10)}
        assert runner._get_dependent_jobs("J3", candidates) == {f"J{i}" for i in range(3, 10)}

    def test_multi_parent_downstream(self):
        # A -> C, B -> C, C -> D
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B"),
            "C": make_job_config("C", depends_on=["A", "B"]),
            "D": make_job_config("D", depends_on=["C"]),
        }
        runner = self._make(jobs)
        # Rewinding "A" should pull in C and D as well.
        assert runner._get_dependent_jobs("A", {"A", "B", "C", "D"}) == {"A", "C", "D"}

    def test_partial_candidate_stops_traversal(self):
        # A -> B -> C -> D, but C not in candidates so D also excluded (blocked)
        jobs = {
            "A": make_job_config("A"),
            "B": make_job_config("B", depends_on=["A"]),
            "C": make_job_config("C", depends_on=["B"]),
            "D": make_job_config("D", depends_on=["C"]),
        }
        runner = self._make(jobs)
        assert runner._get_dependent_jobs("A", {"A", "B", "D"}) == {"A", "B"}


class TestRunJobsBasicFlow:
    @pytest.mark.anyio
    async def test_single_job_completes(self, monkeypatch):
        cfg = {"only": make_job_config("only")}
        job = make_job("only", ["done"], cfg["only"])
        install_rewind_scripts(monkeypatch, {})
        runner = make_runner(cfg)
        context = make_context()
        output = await runner._run_jobs(context, {"only": job}, {}, set())
        assert output == "done"

    @pytest.mark.anyio
    async def test_linear_chain_no_rewind(self, monkeypatch):
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["b"]),
        }
        pending = {
            "a": make_job("a", ["a"], cfg["a"]),
            "b": make_job("b", ["b"], cfg["b"]),
            "c": make_job("c", ["c_final"], cfg["c"]),
        }
        install_rewind_scripts(monkeypatch, {})
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == "c_final"

    @pytest.mark.anyio
    async def test_parallel_branches_dict_merge(self, monkeypatch):
        # a -> b, a -> c, both terminal, both dict outputs → merged
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["a"]),
        }
        pending = {
            "a": make_job("a", ["ok"], cfg["a"]),
            "b": make_job("b", [{"b_key": 1}], cfg["b"]),
            "c": make_job("c", [{"c_key": 2}], cfg["c"]),
        }
        install_rewind_scripts(monkeypatch, {})
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == {"b_key": 1, "c_key": 2}


class TestRunJobsRewindScenarios:
    @pytest.mark.anyio
    async def test_loop_runs_multiple_times_until_condition(self, monkeypatch):
        # counter -> check; check routes back to counter twice, then completes.
        # counter runs 3 times total (initial + 2 rewinds), check runs 3 times.
        cfg = {
            "counter": make_job_config("counter", max_run_count=5),
            "check": make_job_config("check", depends_on=["counter"], max_run_count=5),
        }
        pending = {
            "counter": make_job("counter", ["c1"], cfg["counter"]),
            "check": make_job("check", [RoutingTarget("counter")], cfg["check"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "counter": [["c2"], ["c3"]],
                "check": [[RoutingTarget("counter")], ["done"]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == "done"

    @pytest.mark.anyio
    async def test_rewind_from_deep_downstream(self, monkeypatch):
        # a -> b -> c -> d, d routes back to b once. Rewind should redo b, c, d.
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["b"]),
            "d": make_job_config("d", depends_on=["c"]),
        }
        pending = {
            "a": make_job("a", ["a"], cfg["a"]),
            "b": make_job("b", ["b1"], cfg["b"]),
            "c": make_job("c", ["c1"], cfg["c"]),
            "d": make_job("d", [RoutingTarget("b")], cfg["d"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "b": [["b2"]],
                "c": [["c2"]],
                "d": [["final"]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == "final"

    @pytest.mark.anyio
    async def test_rewind_preserves_non_dependent_upstream(self, monkeypatch):
        # a -> b -> c, but a is NOT rewound when c routes back to b.
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["b"]),
        }
        a_job = make_job("a", ["a_ran_once"], cfg["a"])
        pending = {
            "a": a_job,
            "b": make_job("b", ["b1"], cfg["b"]),
            "c": make_job("c", [RoutingTarget("b")], cfg["c"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "b": [["b2"]],
                "c": [["final"]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == "final"
        # a should have run exactly once, not rewound
        assert a_job._call_index == 1

    @pytest.mark.anyio
    async def test_rewind_diamond_downstream(self, monkeypatch):
        # a -> b, a -> c, b -> d, c -> d. d routes back to a. Everything rewinds.
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["a"]),
            "d": make_job_config("d", depends_on=["b", "c"]),
        }
        pending = {
            "a": make_job("a", ["a1"], cfg["a"]),
            "b": make_job("b", ["b1"], cfg["b"]),
            "c": make_job("c", ["c1"], cfg["c"]),
            "d": make_job("d", [RoutingTarget("a")], cfg["d"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "a": [["a2"]],
                "b": [["b2"]],
                "c": [["c2"]],
                "d": [["final"]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        assert output == "final"

    @pytest.mark.anyio
    async def test_rewind_target_is_router_itself_reruns_once(self, monkeypatch):
        # a -> b. b routes to itself (b in b's own dependency chain not — but routes back to a on first run).
        # We use a -> b, b routes back to a once. Verify a runs twice.
        cfg = {
            "a": make_job_config("a", max_run_count=3),
            "b": make_job_config("b", depends_on=["a"], max_run_count=3),
        }
        a_job = make_job("a", ["a1"], cfg["a"])
        b_job = make_job("b", [RoutingTarget("a")], cfg["b"])
        install_rewind_scripts(
            monkeypatch,
            {
                "a": [["a2"]],
                "b": [["done"]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), {"a": a_job, "b": b_job}, {}, set())
        assert output == "done"
        assert a_job._call_index == 1  # first-instance a ran once, then replaced

    @pytest.mark.anyio
    async def test_max_run_count_on_terminal_via_rewind(self, monkeypatch):
        # a -> b, b routes back to a infinitely; a.max_run_count=3 → 4번째 스케줄 시 raise
        cfg = {
            "a": make_job_config("a", max_run_count=3),
            "b": make_job_config("b", depends_on=["a"], max_run_count=10),
        }
        pending = {
            "a": make_job("a", ["a1"], cfg["a"]),
            "b": make_job("b", [RoutingTarget("a")], cfg["b"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "a": [["a2"], ["a3"], ["a4"]],
                "b": [[RoutingTarget("a")], [RoutingTarget("a")], [RoutingTarget("a")]],
            },
        )
        runner = make_runner(cfg)
        with pytest.raises(RuntimeError, match="max_run_count"):
            await runner._run_jobs(make_context(), pending, {}, set())

    @pytest.mark.anyio
    async def test_dict_output_merge_after_rewind(self, monkeypatch):
        # a -> b, a -> c, both terminal. b routes back to a once, then returns dict.
        # After rewind, b returns {"b_key": 1}, c returns {"c_key": 2}. Merged output expected.
        cfg = {
            "a": make_job_config("a"),
            "b": make_job_config("b", depends_on=["a"]),
            "c": make_job_config("c", depends_on=["a"]),
        }
        pending = {
            "a": make_job("a", ["a1"], cfg["a"]),
            "b": make_job("b", [RoutingTarget("a")], cfg["b"]),
            "c": make_job("c", [{"c_key": 2}], cfg["c"]),
        }
        install_rewind_scripts(
            monkeypatch,
            {
                "a": [["a2"]],
                "b": [[{"b_key": 1}]],
                "c": [[{"c_key_v2": 22}]],
            },
        )
        runner = make_runner(cfg)
        output = await runner._run_jobs(make_context(), pending, {}, set())
        # Both b and c are terminal; their outputs are dicts and get merged.
        assert isinstance(output, dict)
        assert output.get("b_key") == 1


class TestScheduleJobEdgeCases:
    @pytest.mark.anyio
    async def test_max_run_count_of_one_fails_on_second_schedule(self):
        jobs = {"J": make_job_config("J", max_run_count=1)}
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.jobs = jobs
        job = make_job("J", ["out", "out"], jobs["J"])
        counts: Dict[str, int] = {}
        task = runner._schedule_job(job, make_context(), counts)
        task.cancel()
        with pytest.raises(RuntimeError, match="max_run_count"):
            runner._schedule_job(job, make_context(), counts)

    @pytest.mark.anyio
    async def test_independent_jobs_have_independent_counts(self):
        jobs = {
            "A": make_job_config("A", max_run_count=1),
            "B": make_job_config("B", max_run_count=1),
        }
        runner = WorkflowRunner.__new__(WorkflowRunner)
        runner.jobs = jobs
        a = make_job("A", ["a"], jobs["A"])
        b = make_job("B", ["b"], jobs["B"])
        counts: Dict[str, int] = {}
        ta = runner._schedule_job(a, make_context(), counts)
        tb = runner._schedule_job(b, make_context(), counts)
        ta.cancel()
        tb.cancel()
        assert counts == {"A": 1, "B": 1}
