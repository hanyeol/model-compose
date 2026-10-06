"""Parity between controller.run_workflow and controller.resume_workflow for
the wait_for_completion / stop_at_streaming parameters.

Also covers the streaming output lifecycle wiring: a workflow whose output is
a shell-streaming component should surface as STREAMING, and the attached
TaskOutputStreamIterator should round-trip to COMPLETED once consumed.
"""

from __future__ import annotations

import asyncio
import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.base import TaskStatus
from mindor.core.controller.controller import create_controller
from mindor.core.controller.streaming import (
    TaskOutputStreamIterator,
    TaskOutputStreamEncodingIterator,
)
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _build_interrupt_compose() -> ComposeConfig:
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


def _build_streaming_compose() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "lines",
                "type": "shell",
                "action": {
                    "command": [ "sh", "-c", "for i in 1 2 3; do echo line $i; done" ],
                    "streaming": True,
                },
            },
        ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    { "id": "lines", "component": "lines" },
                ],
                "output": "${jobs.lines.output}",
            },
        ],
    })


def _build_streaming_json_compose() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "lines",
                "type": "shell",
                "action": {
                    "command": [ "sh", "-c", "for i in 1 2 3; do echo line $i; done" ],
                    "streaming": True,
                },
            },
        ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [
                    { "id": "lines", "component": "lines" },
                ],
                "output": "${jobs.lines.output as stream/json}",
            },
        ],
    })


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


class TestResumeWaitParity:
    @pytest.mark.anyio
    async def test_resume_without_wait_returns_processing(self):
        controller = _make_controller(_build_interrupt_compose())
        await controller.start()
        try:
            interrupted = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert interrupted.status == TaskStatus.INTERRUPTED

            resumed = await controller.resume_workflow(
                interrupted.task_id,
                interrupted.interrupt.job_id,
                interrupted.interrupt.run_id,
                None,
            )
            assert resumed.status == TaskStatus.PROCESSING

            final = await asyncio.wait_for(
                controller.wait_for_terminal_state(interrupted.task_id),
                timeout=5.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_resume_with_wait_returns_terminal(self):
        controller = _make_controller(_build_interrupt_compose())
        await controller.start()
        try:
            interrupted = await controller.run_workflow("wf", {}, wait_for_completion=True)
            assert interrupted.status == TaskStatus.INTERRUPTED

            final = await asyncio.wait_for(
                controller.resume_workflow(
                    interrupted.task_id,
                    interrupted.interrupt.job_id,
                    interrupted.interrupt.run_id,
                    None,
                    wait_for_completion=True,
                ),
                timeout=5.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()


class TestStreamingOutput:
    @pytest.mark.anyio
    async def test_run_with_stop_at_streaming_yields_stream_iterator(self):
        controller = _make_controller(_build_streaming_compose())
        await controller.start()
        try:
            state = await controller.run_workflow(
                "wf",
                {},
                wait_for_completion=True,
                stop_at_streaming=True,
            )
            assert state.status == TaskStatus.STREAMING
            assert isinstance(state.output, TaskOutputStreamIterator)
            assert not isinstance(state.output, TaskOutputStreamEncodingIterator)

            # Consuming the stream drains lifecycle and transitions to COMPLETED.
            chunks = [ chunk async for chunk in state.output ]
            assert chunks, "expected at least one chunk from the streaming shell"

            final = await asyncio.wait_for(
                controller.wait_for_terminal_state(state.task_id),
                timeout=5.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()

    @pytest.mark.anyio
    async def test_stream_json_cast_wraps_in_encoding_iterator(self):
        controller = _make_controller(_build_streaming_json_compose())
        await controller.start()
        try:
            state = await controller.run_workflow(
                "wf",
                {},
                wait_for_completion=True,
                stop_at_streaming=True,
            )
            assert state.status == TaskStatus.STREAMING
            assert isinstance(state.output, TaskOutputStreamEncodingIterator)

            chunks = [ chunk async for chunk in state.output ]
            assert chunks, "expected at least one encoded chunk"

            final = await asyncio.wait_for(
                controller.wait_for_terminal_state(state.task_id),
                timeout=5.0,
            )
            assert final.status == TaskStatus.COMPLETED
        finally:
            await controller.stop()
