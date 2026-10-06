"""ComposeManager end-to-end coverage: _render_output, _save_output, and
the wait_for_completion lifecycle around run_workflow / resume_workflow.

Shape of the matrix we try to cover:

                      | output_path missing  | output_path given
  ──────────────────── ┼──────────────────── ┼────────────────────
  STREAMING  (stream)  | state.output = iter | file saved, output=None, status=COMPLETED
  STREAMING  (json)    | iter yields json    | file saved w/ json chunks
  COMPLETED  (dict)    | iter yields json    | file saved as JSON
  COMPLETED  (scalar)  | iter yields str     | file saved as str
  INTERRUPTED          | output=None         | (unchanged)
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from mindor.core.component.component import ComponentInstances
from mindor.core.controller.base import TaskStatus
from mindor.core.compose.manager import ComposeManager
from mindor.dsl.schema.compose import ComposeConfig


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def reset_component_instances():
    ComponentInstances.clear()
    yield
    ComponentInstances.clear()


def _compose(workflow_output: str = None, extra_components=None, interrupt: bool = False) -> ComposeConfig:
    components = [
        {
            "id": "lines",
            "type": "shell",
            "action": {
                "command": [ "sh", "-c", "for i in 1 2 3; do echo line $i; done" ],
                "streaming": True,
            },
        },
        {
            "id": "echo_scalar",
            "type": "shell",
            "action": {
                "command": [ "sh", "-c", "echo hello" ],
                "output": "${result.stdout}",
            },
        },
        {
            "id": "echo_dict",
            "type": "shell",
            "action": {
                "command": [ "sh", "-c", "echo hello" ],
                "output": { "greeting": "${result.stdout}", "code": 1 },
            },
        },
    ]
    if extra_components:
        components.extend(extra_components)

    job = { "id": "j", "component": "lines" }
    if interrupt:
        job["interrupt"] = { "before": { "message": "waiting" } }

    workflow = {
        "id": "wf",
        "jobs": [ job ],
    }
    if workflow_output is not None:
        workflow["output"] = workflow_output

    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": components,
        "workflows": [ workflow ],
    })


def _compose_scalar() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "echo_scalar",
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
                "jobs": [ { "id": "j", "component": "echo_scalar" } ],
                "output": "${jobs.j.output}",
            },
        ],
    })


def _compose_dict() -> ComposeConfig:
    return ComposeConfig.model_validate({
        "controller": {
            "runtime": "native",
            "max_concurrent_count": 0,
            "adapters": [],
        },
        "components": [
            {
                "id": "echo_dict",
                "type": "shell",
                "action": {
                    "command": [ "sh", "-c", "echo hello" ],
                    "output": { "greeting": "${result.stdout}" },
                },
            },
        ],
        "workflows": [
            {
                "id": "wf",
                "jobs": [ { "id": "j", "component": "echo_dict" } ],
                "output": "${jobs.j.output}",
            },
        ],
    })


def _compose_stream(workflow_output: str = "${jobs.j.output}") -> ComposeConfig:
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
                "jobs": [ { "id": "j", "component": "lines" } ],
                "output": workflow_output,
            },
        ],
    })


def _compose_interrupt() -> ComposeConfig:
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
                        "id": "j",
                        "component": "echo",
                        "interrupt": { "before": { "message": "waiting" } },
                    },
                ],
                "output": "${jobs.j.output}",
            },
        ],
    })


class TestRenderOutputStdoutPath:
    """output_path 가 없을 때 manager 가 state.output 을 lazy async iterator 로 교체하는지."""

    @pytest.mark.anyio
    async def test_scalar_output_yields_single_str_chunk(self):
        manager = ComposeManager(_compose_scalar(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.COMPLETED
            assert state.output is not None

            chunks = [ chunk async for chunk in state.output ]
            assert len(chunks) == 1
            assert isinstance(chunks[0], str)
            assert "hello" in chunks[0]
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_dict_output_yields_json_string(self):
        manager = ComposeManager(_compose_dict(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.COMPLETED

            chunks = [ chunk async for chunk in state.output ]
            assert len(chunks) == 1
            assert isinstance(chunks[0], str)
            # dict is json-encoded, not str()
            parsed = json.loads(chunks[0])
            assert "greeting" in parsed
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_stream_output_yields_chunks_and_streaming_status(self):
        manager = ComposeManager(_compose_stream(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.STREAMING
            assert state.output is not None

            chunks = [ chunk async for chunk in state.output ]
            # shell streaming yields bytes
            assert chunks, "expected at least one chunk from streaming shell"

            # After consumption, lifecycle hook fires COMPLETED — caller needs
            # to call wait_for_completion.
            final = await manager.wait_for_completion(state)
            assert final.status == TaskStatus.COMPLETED
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_stream_json_cast_yields_json_strings(self):
        manager = ComposeManager(
            _compose_stream("${jobs.j.output as stream/json}"),
            daemon=False,
        )
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.STREAMING

            chunks = [ chunk async for chunk in state.output ]
            # Encoded as JSON strings by StreamEncodingIterator
            assert chunks
            for c in chunks:
                assert isinstance(c, str)

            final = await manager.wait_for_completion(state)
            assert final.status == TaskStatus.COMPLETED
        finally:
            await manager.controller.stop()


class TestRenderOutputFilePath:
    """output_path 가 있을 때 manager 가 파일에 저장하고 output 을 None 으로 꺼두는지."""

    @pytest.mark.anyio
    async def test_scalar_saved_as_text(self, tmp_path: Path):
        manager = ComposeManager(_compose_scalar(), daemon=False)
        try:
            out = tmp_path / "out.txt"
            state = await manager.run_workflow("wf", {}, str(out), False)
            assert state.status == TaskStatus.COMPLETED
            assert state.output is None
            assert "hello" in out.read_text()
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_dict_saved_as_json(self, tmp_path: Path):
        manager = ComposeManager(_compose_dict(), daemon=False)
        try:
            out = tmp_path / "out.json"
            state = await manager.run_workflow("wf", {}, str(out), False)
            assert state.status == TaskStatus.COMPLETED
            assert state.output is None

            parsed = json.loads(out.read_text())
            assert "greeting" in parsed
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_stream_saved_and_transitions_to_completed(self, tmp_path: Path):
        manager = ComposeManager(_compose_stream(), daemon=False)
        try:
            out = tmp_path / "lines.txt"
            # output_path path: manager drains the stream itself.
            # But it does NOT call wait_for_completion anymore (per recent refactor).
            state = await manager.run_workflow("wf", {}, str(out), False)
            # Stream drained → lifecycle fires COMPLETED, so status could be STREAMING
            # or COMPLETED depending on timing. The point is: output is None, file written.
            assert state.output is None

            body = out.read_bytes()
            assert b"line 1" in body
            assert b"line 2" in body
            assert b"line 3" in body

            # Caller still finalizes lifecycle via wait_for_completion when STREAMING.
            if state.status == TaskStatus.STREAMING:
                state = await manager.wait_for_completion(state)
            assert state.status == TaskStatus.COMPLETED
        finally:
            await manager.controller.stop()


class TestResumeWorkflowOutput:
    """resume_workflow 도 run_workflow 와 같은 output 처리 contract 를 따르는지."""

    @pytest.mark.anyio
    async def test_resume_without_output_path_yields_iterator(self):
        manager = ComposeManager(_compose_interrupt(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.INTERRUPTED
            assert state.output is None

            resumed = await manager.resume_workflow(
                state.task_id,
                state.interrupt.job_id,
                state.interrupt.run_id,
                None,
                output_path=None,
            )
            assert resumed.status == TaskStatus.COMPLETED
            assert resumed.output is not None

            chunks = [ chunk async for chunk in resumed.output ]
            assert any("hello" in c for c in chunks if isinstance(c, str))
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_resume_with_output_path_saves(self, tmp_path: Path):
        manager = ComposeManager(_compose_interrupt(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.INTERRUPTED

            out = tmp_path / "resumed.txt"
            resumed = await manager.resume_workflow(
                state.task_id,
                state.interrupt.job_id,
                state.interrupt.run_id,
                None,
                output_path=str(out),
            )
            assert resumed.status == TaskStatus.COMPLETED
            assert resumed.output is None
            assert "hello" in out.read_text()
        finally:
            await manager.controller.stop()


class TestWaitForCompletion:
    """wait_for_completion 이 호출자용 공용 라이프사이클 메서드로 작동하는지."""

    @pytest.mark.anyio
    async def test_wait_after_stream_consumption(self):
        manager = ComposeManager(_compose_stream(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            assert state.status == TaskStatus.STREAMING

            # Consume
            chunks = [ chunk async for chunk in state.output ]
            assert chunks

            final = await asyncio.wait_for(manager.wait_for_completion(state), timeout=5.0)
            assert final.status == TaskStatus.COMPLETED
            assert final.task_id == state.task_id
        finally:
            await manager.controller.stop()

    @pytest.mark.anyio
    async def test_wait_on_already_terminal_state_returns_immediately(self):
        """`wait_for_terminal_state` is idempotent on already-terminal states."""
        manager = ComposeManager(_compose_scalar(), daemon=False)
        try:
            state = await manager.run_workflow("wf", {}, None, False)
            # COMPLETED already
            assert state.status == TaskStatus.COMPLETED

            # Even though wait_for_completion is "STREAMING-presumed", calling it on
            # COMPLETED must not deadlock.
            final = await asyncio.wait_for(manager.wait_for_completion(state), timeout=1.0)
            assert final.status == TaskStatus.COMPLETED
        finally:
            await manager.controller.stop()
