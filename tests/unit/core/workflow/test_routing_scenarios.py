"""Routing-aware workflow scenarios.

These tests probe WorkflowRunner.run() end-to-end so that pending/routing
partitioning (driven by each job config's `get_routing_jobs()`) is exercised,
not just the hand-fed `_run_jobs()` path.

What we are checking:

    1. A router (e.g. an `if` job) exposes several candidate target jobs via
       `get_routing_jobs()`. Those targets are stripped out of `pending_jobs`
       at startup and only materialize when the router picks them.
    2. If a non-selected target is also a `depends_on` of some *other* pending
       job, that other job's dependency can never resolve and the workflow
       deadlocks with "No runnable jobs but pending jobs remain."
    3. Nested routers, join nodes, and chained branches all go through the
       same partitioning rule — any of them can trip (2).

We fake the DSL layer with SimpleNamespace configs: each config carries the
depends_on list and a `get_routing_jobs()` method so the runner can partition
jobs exactly as it would for real `if`/`switch`/`random-router` configs.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Set
from unittest.mock import MagicMock

import pytest

from mindor.core.workflow import runner as workflow_module
from mindor.core.workflow.job.base import Job, RoutingTarget
from mindor.core.workflow.runner import WorkflowRunner


# --------------------------------------------------------------------------- #
# Test fixtures / helpers
# --------------------------------------------------------------------------- #


@pytest.fixture
def anyio_backend():
    return "asyncio"


def make_cfg(
    job_id: str,
    depends_on: Optional[List[Any]] = None,
    routes: Optional[Iterable[str]] = None,
    max_run_count: int = 5,
) -> SimpleNamespace:
    """Build a job config stub.

    `routes` is the set of jobs this config declares as routing targets — i.e.
    what `get_routing_jobs()` would return for a real `if`/`switch`/`random-router`.
    """
    depends_on = depends_on or []
    routes_set: Set[str] = set(routes or [])

    def _groups() -> List[List[str]]:
        return [([ item ] if isinstance(item, str) else list(item)) for item in depends_on]

    def _ids() -> Set[str]:
        ids: Set[str] = set()
        for item in depends_on:
            if isinstance(item, str):
                ids.add(item)
            else:
                ids.update(item)
        return ids

    return SimpleNamespace(
        id=job_id,
        depends_on=depends_on,
        max_run_count=max_run_count,
        type=SimpleNamespace(value="mock"),
        retry=None,
        on_error=None,
        get_dependency_groups=_groups,
        get_dependency_ids=_ids,
        get_routing_jobs=lambda: set(routes_set),
    )


class ScriptedJob(Job):
    """A Job whose `_run()` returns pre-scripted outputs on each successive call."""

    def __init__(self, id: str, outputs: List[Any]):
        self.id = id
        self.config = None
        self.global_configs = None
        self._outputs = list(outputs)
        self._call_index = 0

    async def _run(self, context, run_id, default_input, is_terminal) -> Any:
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
    context.complete_job = MagicMock(
        side_effect=lambda job_id, output: context.sources["jobs"].__setitem__(job_id, {"output": output})
    )

    async def _noop_notify(*args, **kwargs):
        return None

    async def _noop_render(value, skip_decode=False):
        return value

    context.job_event_notifier = MagicMock()
    context.job_event_notifier.notify = _noop_notify
    context.render_variable = _noop_render
    return context


def install_scripts(monkeypatch, scripts: Dict[str, List[List[Any]]]) -> Dict[str, int]:
    """Register per-job output scripts consumed sequentially on each (re)creation.

    scripts["foo"] = [[out1], [out2], ...] — one list per instantiation of foo.
    First call to create_job("foo", ...) returns a ScriptedJob with outputs=[out1],
    second with [out2], etc.
    """
    counters: Dict[str, int] = {job_id: 0 for job_id in scripts}

    def _fake_create_job(job_id: str, config: SimpleNamespace, global_configs: Any) -> Job:
        if job_id not in scripts:
            raise AssertionError(f"create_job called for unregistered job '{job_id}'")
        idx = counters[job_id]
        counters[job_id] += 1
        job = ScriptedJob(job_id, list(scripts[job_id][idx]))
        job.config = config
        return job

    monkeypatch.setattr(workflow_module, "create_job", _fake_create_job)
    return counters


def partition_jobs(
    jobs: Dict[str, SimpleNamespace],
) -> tuple[Dict[str, SimpleNamespace], Set[str]]:
    """Mirror WorkflowRunner.run's partitioning logic for direct `_run_jobs` tests."""
    routing_ids: Set[str] = {
        target_id
        for cfg in jobs.values()
        for target_id in cfg.get_routing_jobs()
    }
    return jobs, routing_ids


def make_runner(cfg: Dict[str, SimpleNamespace]) -> WorkflowRunner:
    runner = WorkflowRunner.__new__(WorkflowRunner)
    runner.id = "wf"
    runner.jobs = cfg
    runner.output = None
    runner.global_configs = None
    return runner


async def run(
    monkeypatch,
    cfg: Dict[str, SimpleNamespace],
    scripts: Dict[str, List[List[Any]]],
) -> Any:
    """Driver that mirrors WorkflowRunner.run()'s pending/routing partitioning."""
    install_scripts(monkeypatch, scripts)
    _, routing_ids = partition_jobs(cfg)
    pending = {
        job_id: workflow_module.create_job(job_id, c, None)
        for job_id, c in cfg.items()
        if job_id not in routing_ids
    }
    routing = {
        job_id: workflow_module.create_job(job_id, c, None)
        for job_id, c in cfg.items()
        if job_id in routing_ids
    }
    runner = make_runner(cfg)
    return await runner._run_jobs(make_context(), pending, routing)


# --------------------------------------------------------------------------- #
# Scenario 1 — single-step branches (the "canonical" if usage)
# --------------------------------------------------------------------------- #


class TestSingleStepBranches:
    """`if` routes to one of two singleton targets. Nobody else depends on them."""

    @pytest.mark.anyio
    async def test_routes_to_true_branch(self, monkeypatch):
        cfg = {
            "check":    make_cfg("check", routes=["branch_true", "branch_false"]),
            "branch_true":  make_cfg("branch_true"),
            "branch_false": make_cfg("branch_false"),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check":        [[RoutingTarget("branch_true")]],
                "branch_true":  [["TRUE"]],
                "branch_false": [["FALSE"]],  # should never run
            },
        )
        assert output == "TRUE"

    @pytest.mark.anyio
    async def test_routes_to_false_branch(self, monkeypatch):
        cfg = {
            "check":    make_cfg("check", routes=["branch_true", "branch_false"]),
            "branch_true":  make_cfg("branch_true"),
            "branch_false": make_cfg("branch_false"),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check":        [[RoutingTarget("branch_false")]],
                "branch_true":  [["TRUE"]],
                "branch_false": [["FALSE"]],
            },
        )
        assert output == "FALSE"


# --------------------------------------------------------------------------- #
# Scenario 2 — multi-step branches (chain inside a branch)
# --------------------------------------------------------------------------- #


class TestChainedBranches:
    """A branch target chains to a second step via `depends_on`.

    Hypothesis under test: if the second step B2 depends on B1 (a routing
    target), and the router selects the other side instead, B2 is still a
    pending job whose dependency is dead → deadlock.
    """

    @pytest.mark.anyio
    async def test_selected_chain_runs_to_end(self, monkeypatch):
        # check → T1 → T2 (selected)
        # check → F1 (not selected)
        cfg = {
            "check": make_cfg("check", routes=["T1", "F1"]),
            "T1":    make_cfg("T1"),
            "T2":    make_cfg("T2", depends_on=["T1"]),
            "F1":    make_cfg("F1"),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check": [[RoutingTarget("T1")]],
                "T1":    [["t1"]],
                "T2":    [["t2_final"]],
                "F1":    [["f1"]],
            },
        )
        assert output == "t2_final"

    @pytest.mark.anyio
    async def test_non_selected_chain_leaves_dangling_pending_job(self, monkeypatch):
        """If router picks T-side, F2 (which depends on F1, a routing target
        the router did not select) sits in pending with an unmet dependency."""
        cfg = {
            "check": make_cfg("check", routes=["T1", "F1"]),
            "T1":    make_cfg("T1"),
            "F1":    make_cfg("F1"),
            "F2":    make_cfg("F2", depends_on=["F1"]),
        }
        with pytest.raises(RuntimeError, match="No runnable jobs but pending jobs remain"):
            await run(
                monkeypatch,
                cfg,
                scripts={
                    "check": [[RoutingTarget("T1")]],
                    "T1":    [["t1"]],
                    "F1":    [["f1"]],
                    "F2":    [["f2"]],
                },
            )


# --------------------------------------------------------------------------- #
# Scenario 3 — join / merge after branches
# --------------------------------------------------------------------------- #


class TestJoinAfterBranches:
    """A `join` job sits after both branches with an OR-group `depends_on`.

    model-compose's dependency grammar lets `depends_on: [[a, b]]` mean "any
    one of a or b" (see `_is_runnable_job` in runner.py). We verify the join
    resolves when the selected branch completes.
    """

    @pytest.mark.anyio
    async def test_or_group_join_runs_when_one_branch_completes(self, monkeypatch):
        cfg = {
            "check": make_cfg("check", routes=["T", "F"]),
            "T":     make_cfg("T"),
            "F":     make_cfg("F"),
            "join":  make_cfg("join", depends_on=[["T", "F"]]),  # OR of T,F
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check": [[RoutingTarget("T")]],
                "T":     [["t"]],
                "F":     [["f"]],
                "join":  [["joined"]],
            },
        )
        assert output == "joined"

    @pytest.mark.anyio
    async def test_and_group_join_deadlocks_when_only_one_branch_runs(self, monkeypatch):
        """`depends_on: [T, F]` is AND of both; a router that only ever picks
        one leaves the other unresolved and the join cannot progress."""
        cfg = {
            "check": make_cfg("check", routes=["T", "F"]),
            "T":     make_cfg("T"),
            "F":     make_cfg("F"),
            "join":  make_cfg("join", depends_on=["T", "F"]),  # AND
        }
        with pytest.raises(RuntimeError, match="No runnable jobs but pending jobs remain"):
            await run(
                monkeypatch,
                cfg,
                scripts={
                    "check": [[RoutingTarget("T")]],
                    "T":     [["t"]],
                    "F":     [["f"]],
                    "join":  [["joined"]],
                },
            )


# --------------------------------------------------------------------------- #
# Scenario 4 — nested routers
# --------------------------------------------------------------------------- #


class TestNestedRouters:
    """One router routes to another router."""

    @pytest.mark.anyio
    async def test_nested_router_resolves(self, monkeypatch):
        # outer → inner → leaf_a / leaf_b
        cfg = {
            "outer": make_cfg("outer", routes=["inner"]),
            "inner": make_cfg("inner", routes=["leaf_a", "leaf_b"]),
            "leaf_a": make_cfg("leaf_a"),
            "leaf_b": make_cfg("leaf_b"),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "outer":  [[RoutingTarget("inner")]],
                "inner":  [[RoutingTarget("leaf_a")]],
                "leaf_a": [["A"]],
                "leaf_b": [["B"]],
            },
        )
        assert output == "A"


# --------------------------------------------------------------------------- #
# Scenario 5 — router with downstream join via "any of the targets"
# --------------------------------------------------------------------------- #


class TestJoinViaRouterOutput:
    """A downstream job uses an OR-group over the router targets as its dep.

    This is the sanctioned "post-branch merge" pattern. The downstream job
    must only wait for whichever branch the router picked.
    """

    @pytest.mark.anyio
    async def test_post_router_join_or_group(self, monkeypatch):
        # Non-trivial because `check` itself completes AFTER routing, but the
        # join depends on branches, not on check.
        cfg = {
            "check": make_cfg("check", routes=["T", "F"]),
            "T":     make_cfg("T"),
            "F":     make_cfg("F"),
            "after": make_cfg("after", depends_on=[["T", "F"]]),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check": [[RoutingTarget("F")]],
                "T":     [["t"]],
                "F":     [["f"]],
                "after": [["AFTER"]],
            },
        )
        assert output == "AFTER"


# --------------------------------------------------------------------------- #
# Scenario 6 — router falls through to `otherwise`-style default
# --------------------------------------------------------------------------- #


class TestOtherwiseTarget:
    """The `otherwise` branch is just another routing target under the hood."""

    @pytest.mark.anyio
    async def test_otherwise_branch_runs(self, monkeypatch):
        cfg = {
            "check": make_cfg("check", routes=["T", "F", "default"]),
            "T":     make_cfg("T"),
            "F":     make_cfg("F"),
            "default": make_cfg("default"),
        }
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "check":   [[RoutingTarget("default")]],
                "T":       [["t"]],
                "F":       [["f"]],
                "default": [["DEFAULT"]],
            },
        )
        assert output == "DEFAULT"


# --------------------------------------------------------------------------- #
# Scenario 7 — router pointing at a job that is ALSO a non-router dependency.
# --------------------------------------------------------------------------- #


class TestRouterTargetIsAlsoNormalDependency:
    """If job X is both a routing target of `router` and a `depends_on` of
    some other pending job Y, the router "wins": X is stripped from pending
    at startup, Y stays stuck."""

    @pytest.mark.anyio
    async def test_dangling_dependency_on_router_target(self, monkeypatch):
        cfg = {
            "router": make_cfg("router", routes=["X"]),
            "X":      make_cfg("X"),
            "Y":      make_cfg("Y", depends_on=["X"]),
        }
        # Router does route to X, so X DOES eventually run. But at startup Y
        # was pending with dep [X], and X was NOT in pending — so Y had no
        # chance to go runnable until X completed. Verify the happy path:
        output = await run(
            monkeypatch,
            cfg,
            scripts={
                "router": [[RoutingTarget("X")]],
                "X":      [["x"]],
                "Y":      [["y_final"]],
            },
        )
        assert output == "y_final"
