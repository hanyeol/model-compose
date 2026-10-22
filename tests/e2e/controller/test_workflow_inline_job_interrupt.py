"""E2E tests for interrupts declared on inline jobs (pipeline steps, etc.).

Regression for #70: before the fix, the runner matched the Point's `job_id`
(e.g. `steps[step:1]`) against `running_job_ids` which only holds top-level
ids (`steps`). The subset check never passed, so the batched interrupt was
never flushed and the workflow hung forever.
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


def _echo_component(id: str = "echo") -> dict:
    return {
        "id": id,
        "type": "shell",
        "action": {
            "command": [ "sh", "-c", "echo hello" ],
            "output": "${result.stdout}",
        },
    }


def _pipeline_step_interrupt_compose() -> ComposeConfig:
    """A pipeline job whose second step declares `interrupt.before`."""
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
                        "id": "steps",
                        "type": "pipeline",
                        "steps": [
                            { "component": "echo" },
                            {
                                "component": "echo",
                                "interrupt": {
                                    "before": { "message": "Resume to continue." },
                                },
                            },
                        ],
                    },
                ],
            },
        ],
    })


class TestInlineJobInterrupt:
    @pytest.mark.anyio
    async def test_pipeline_step_interrupt_surfaces_as_batched_interrupt(self):
        controller = _make_controller(_pipeline_step_interrupt_compose())
        await controller.start()
        try:
            state = await asyncio.wait_for(
                controller.run_workflow("wf", {}, wait_for_completion=True),
                timeout=10.0,
            )
            assert state.status == TaskStatus.INTERRUPTED
            assert isinstance(state.interrupt, list)
            assert len(state.interrupt) == 1
            assert state.interrupt[0].phase == "before"
            assert state.interrupt[0].message == "Resume to continue."
            # The inline id surfaces to the client untouched; only the runner's
            # quiescence bookkeeping folds it onto the top-level job.
            assert state.interrupt[0].job_id.startswith("steps[")
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_resume_from_pipeline_step_interrupt_completes_workflow(self):
        controller = _make_controller(_pipeline_step_interrupt_compose())
        await controller.start()
        try:
            state = await asyncio.wait_for(
                controller.run_workflow("wf", {}, wait_for_completion=True),
                timeout=10.0,
            )
            assert state.status == TaskStatus.INTERRUPTED

            final = await asyncio.wait_for(
                controller.resume_workflow(
                    state.task_id,
                    answer={ state.interrupt[0].id: None },
                    wait_for_completion=True,
                ),
                timeout=10.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()
