"""Smoke test: cancel_workflow while the task is INTERRUPTED.

Boots a minimal ControllerService, runs a shell job that has an `interrupt.before`
point, waits until the task reaches INTERRUPTED, then calls cancel_workflow and
asserts that the task actually transitions to CANCELLED (not stuck).
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


def _build_compose() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "echo",
                "type": "shell",
                "action": {
                    "command": [ "sh", "-c", "echo hello" ],
                    "output": "${result.stdout}",
                },
            },
        ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    {
                        "id": "j1",
                        "component": "echo",
                        "interrupt": {
                            "before": {
                                "message": "waiting",
                            },
                        },
                    },
                ],
            },
        ],
    })


class TestInterruptCancel:
    @pytest.mark.anyio
    async def test_cancel_while_interrupted_transitions_to_cancelled(self):
        compose = _build_compose()
        controller = create_controller(
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
        await controller.start()
        try:
            # Kick off; will pause at the `before` interrupt.
            interrupted = await controller.run_workflow(
                workflow_id="wf",
                input={},
                wait_for_completion=True,  # returns as soon as INTERRUPTED is reached
            )

            assert interrupted.status == TaskStatus.INTERRUPTED, (
                f"Expected INTERRUPTED, got {interrupted.status}: {interrupted.error}"
            )
            task_id = interrupted.task_id

            # Cancel from the INTERRUPTED state.
            cancelled = await asyncio.wait_for(
                controller.cancel_workflow(task_id, wait_for_completion=True),
                timeout=5.0,
            )

            assert cancelled.status == TaskStatus.CANCELLED, (
                f"Expected CANCELLED, got {cancelled.status}: {cancelled.error}"
            )

            # Double-check via the terminal-state waiter.
            final = await asyncio.wait_for(
                controller.wait_for_terminal_state(task_id),
                timeout=5.0,
            )
            assert final.status == TaskStatus.CANCELLED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_cancel_while_interrupted_non_blocking(self):
        """Same as above but with wait_for_completion=False (matches the webui path)."""
        compose = _build_compose()
        controller = create_controller(
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
        await controller.start()
        try:
            interrupted = await controller.run_workflow(
                workflow_id="wf",
                input={},
                wait_for_completion=True,
            )
            assert interrupted.status == TaskStatus.INTERRUPTED
            task_id = interrupted.task_id

            # Fire-and-forget cancel — matches the webui `_cancel_workflow` call path.
            await controller.cancel_workflow(task_id, wait_for_completion=False)

            # Now wait for the terminal state separately (webui relies on the still-alive
            # _run_workflow generator to observe this).
            final = await asyncio.wait_for(
                controller.wait_for_terminal_state(task_id),
                timeout=5.0,
            )
            assert final.status == TaskStatus.CANCELLED, (
                f"Expected CANCELLED, got {final.status}: {final.error}"
            )
        finally:
            await controller.stop()
