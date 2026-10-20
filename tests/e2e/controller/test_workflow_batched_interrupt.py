"""E2E tests for the batched workflow interrupt mechanism.

Covers the unified interrupt envelope: `TaskState.interrupt` is always a
`List[InterruptState]` (or None), each entry carries a stable `id`, and
`resume_workflow` resolves points by id with partial-resume semantics
(LangGraph-style).

Scenarios:
1. Two parallel Jobs each with `interrupt.before` are surfaced in a single
   batched INTERRUPTED state.
2. Resuming all points at once completes the workflow.
3. Partial resume keeps the task INTERRUPTED with only the unresolved points.
4. A single-Job interrupt still presents as a length-1 list.
5. Cancel during batched interrupt drains all pending points to CANCELLED.
6. Mixed phase (`before` + `after`) points coexist in one batch.
7. Dependency chain: A → (B, C parallel). Both B and C interrupt → batch of 2.
8. Unknown ids in `answer` are silently ignored.
9. Empty `answer` leaves the task INTERRUPTED with the full list intact.
"""

from __future__ import annotations

import asyncio
import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.base import TaskStatus
from mindor.core.controller.controller import create_controller
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _make_controller(compose: ComposeConfig):
    return create_controller(
        compose.controller,
        compose.workflows,
        compose.components,
        compose.systems,
        compose.listeners,
        compose.gateways,
        compose.tracers,
        compose.loggers,
        daemon=False,
    )


def _echo_component(id: str = "echo", message: str = "hello") -> dict:
    return {
        "id": id,
        "type": "shell",
        "action": {
            "command": [ "sh", "-c", f"echo {message}" ],
            "output": "${result.stdout}",
        },
    }


def _parallel_interrupt_before_compose() -> ComposeConfig:
    """Two independent Jobs, each pauses at `interrupt.before`."""
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [ _echo_component() ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    {
                        "id": "move_a",
                        "component": "echo",
                        "interrupt": {
                            "before": {
                                "message": "Approve moving a.txt?",
                                "metadata": { "target": "a.txt" },
                            },
                        },
                    },
                    {
                        "id": "move_b",
                        "component": "echo",
                        "interrupt": {
                            "before": {
                                "message": "Approve moving b.txt?",
                                "metadata": { "target": "b.txt" },
                            },
                        },
                    },
                ],
            },
        ],
    })


def _single_interrupt_compose() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [ _echo_component() ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    {
                        "id": "only_job",
                        "component": "echo",
                        "interrupt": {
                            "before": {
                                "message": "Approve?",
                                "metadata": { "key": "value" },
                            },
                        },
                    },
                ],
            },
        ],
    })


def _mixed_phase_compose() -> ComposeConfig:
    """Two parallel Jobs: one `before`, one `after`."""
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [ _echo_component() ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    {
                        "id": "before_job",
                        "component": "echo",
                        "interrupt": {
                            "before": { "message": "before-pause" },
                        },
                    },
                    {
                        "id": "after_job",
                        "component": "echo",
                        "interrupt": {
                            "after": { "message": "after-pause" },
                        },
                    },
                ],
            },
        ],
    })


def _chain_then_parallel_compose() -> ComposeConfig:
    """A → (B, C parallel). B and C both have `interrupt.before`."""
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [ _echo_component() ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    { "id": "a", "component": "echo" },
                    {
                        "id": "b",
                        "component": "echo",
                        "depends_on": [ "a" ],
                        "interrupt": {
                            "before": { "message": "approve-b" },
                        },
                    },
                    {
                        "id": "c",
                        "component": "echo",
                        "depends_on": [ "a" ],
                        "interrupt": {
                            "before": { "message": "approve-c" },
                        },
                    },
                ],
            },
        ],
    })


def _by_job_id(interrupts: list, job_id: str):
    matches = [ i for i in interrupts if i.job_id == job_id ]
    assert len(matches) == 1, f"expected exactly one interrupt for job '{job_id}', got {len(matches)}"
    return matches[0]


class TestBatchedInterrupt:
    @pytest.mark.anyio
    async def test_two_parallel_interrupts_surface_as_batch(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert isinstance(state.interrupt, list)
            assert len(state.interrupt) == 2

            move_a = _by_job_id(state.interrupt, "move_a")
            move_b = _by_job_id(state.interrupt, "move_b")

            assert move_a.phase == "before"
            assert move_a.message == "Approve moving a.txt?"
            assert move_a.metadata == { "target": "a.txt" }
            assert isinstance(move_a.id, str) and move_a.id

            assert move_b.phase == "before"
            assert move_b.metadata == { "target": "b.txt" }
            assert move_a.id != move_b.id
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_resume_all_points_completes_workflow(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED

            answers = { point.id: None for point in state.interrupt }
            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer=answers,
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_partial_resume_keeps_task_interrupted(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert len(state.interrupt) == 2

            move_a = _by_job_id(state.interrupt, "move_a")
            move_b = _by_job_id(state.interrupt, "move_b")

            # Resolve only move_a.
            partial = await controller.resume_workflow(
                state.task_id,
                answer={ move_a.id: None },
            )
            assert partial.status == TaskStatus.INTERRUPTED, (
                f"expected INTERRUPTED after partial resume, got {partial.status}"
            )
            assert isinstance(partial.interrupt, list)
            assert len(partial.interrupt) == 1
            assert partial.interrupt[0].id == move_b.id
            assert partial.interrupt[0].job_id == "move_b"

            # Second resume completes the workflow.
            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer={ move_b.id: None },
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_single_interrupt_is_length_one_list(self):
        controller = _make_controller(_single_interrupt_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert isinstance(state.interrupt, list)
            assert len(state.interrupt) == 1

            only = state.interrupt[0]
            assert only.job_id == "only_job"
            assert only.phase == "before"
            assert only.message == "Approve?"
            assert only.metadata == { "key": "value" }
            assert isinstance(only.id, str) and only.id

            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer={ only.id: None },
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_cancel_during_batched_interrupt_drains_all(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert len(state.interrupt) == 2

            cancelled = await asyncio.wait_for(
                controller.cancel_workflow(state.task_id, wait_for_completion=True),
                timeout=5.0,
            )
            assert cancelled.status == TaskStatus.CANCELLED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_mixed_phase_coexist_in_batch(self):
        controller = _make_controller(_mixed_phase_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert len(state.interrupt) == 2

            before = _by_job_id(state.interrupt, "before_job")
            after = _by_job_id(state.interrupt, "after_job")
            assert before.phase == "before"
            assert after.phase == "after"

            answers = { before.id: None, after.id: None }
            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer=answers,
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_dependency_chain_then_parallel_batch(self):
        controller = _make_controller(_chain_then_parallel_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert len(state.interrupt) == 2

            b = _by_job_id(state.interrupt, "b")
            c = _by_job_id(state.interrupt, "c")
            assert b.message == "approve-b"
            assert c.message == "approve-c"

            answers = { b.id: None, c.id: None }
            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer=answers,
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_unknown_ids_in_answer_are_ignored(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED

            move_a = _by_job_id(state.interrupt, "move_a")
            move_b = _by_job_id(state.interrupt, "move_b")

            answers = {
                move_a.id: None,
                move_b.id: None,
                "non-existent-id-01HZZZZZZZZZZZZZZZZZZZZZZ": "ghost",
            }
            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer=answers,
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_empty_answer_leaves_task_interrupted(self):
        controller = _make_controller(_parallel_interrupt_before_compose())
        await controller.start()
        try:
            state = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert state.status == TaskStatus.INTERRUPTED
            assert len(state.interrupt) == 2
            ids_before = { point.id for point in state.interrupt }

            same = await controller.resume_workflow(state.task_id, answer={})
            assert same.status == TaskStatus.INTERRUPTED
            assert isinstance(same.interrupt, list)
            assert len(same.interrupt) == 2
            assert { point.id for point in same.interrupt } == ids_before
        finally:
            await controller.stop()
