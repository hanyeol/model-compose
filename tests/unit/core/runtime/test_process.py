"""Unit tests for `core/runtime/process.py` (lifecycle only).

Scope: `ProcessRuntime` spawns/stops a `multiprocessing.Process`; `ProcessRuntimeParams`
carries env/timeouts. The class knows nothing about IPC protocols — callers wire any
transport (e.g., Queues) and pass the entry point via `target`/`args`.
"""

from __future__ import annotations

import asyncio
import os
import time
from multiprocessing import Process, Queue

import pytest

from mindor.core.runtime.process import ProcessRuntime, ProcessRuntimeParams


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Module-level child entry points (must be picklable for `spawn` start method)
# ---------------------------------------------------------------------------

def _exit_immediately() -> None:
    return


def _echo_via_queue(out_q: Queue, value: str) -> None:
    out_q.put(value)


def _sleep_forever() -> None:
    time.sleep(3600)


def _read_env_var(out_q: Queue, name: str) -> None:
    out_q.put(os.environ.get(name, "<missing>"))


# ---------------------------------------------------------------------------
# ProcessRuntimeParams
# ---------------------------------------------------------------------------

class TestProcessRuntimeParams:
    def test_default_values(self):
        params = ProcessRuntimeParams()
        assert params.env == {}
        assert params.start_timeout == 60.0
        assert params.stop_timeout == 30.0

    def test_custom_values(self):
        params = ProcessRuntimeParams(
            env={"FOO": "bar"},
            start_timeout=10.0,
            stop_timeout=5.0,
        )
        assert params.env == {"FOO": "bar"}
        assert params.start_timeout == 10.0
        assert params.stop_timeout == 5.0


# ---------------------------------------------------------------------------
# ProcessRuntime lifecycle
# ---------------------------------------------------------------------------

class TestProcessRuntimeLifecycle:
    @pytest.mark.anyio
    async def test_initial_state(self):
        runtime = ProcessRuntime(target=_exit_immediately, args=(), params=ProcessRuntimeParams())
        assert runtime.subprocess is None
        assert runtime.is_alive is False

    @pytest.mark.anyio
    async def test_start_spawns_subprocess(self):
        runtime = ProcessRuntime(target=_exit_immediately, args=(), params=ProcessRuntimeParams())
        await runtime.start()
        try:
            assert isinstance(runtime.subprocess, Process)
            # The child either is alive momentarily or has already exited cleanly.
            runtime.subprocess.join(timeout=5.0)
            assert runtime.subprocess.exitcode == 0
        finally:
            await runtime.stop()
            assert runtime.is_alive is False

    @pytest.mark.anyio
    async def test_args_are_passed_to_target(self):
        out_q: Queue = Queue()
        runtime = ProcessRuntime(target=_echo_via_queue, args=(out_q, "hello"), params=ProcessRuntimeParams())
        await runtime.start()
        try:
            assert out_q.get(timeout=5.0) == "hello"
        finally:
            await runtime.stop()

    @pytest.mark.anyio
    async def test_stop_terminates_running_child(self):
        runtime = ProcessRuntime(
            target=_sleep_forever,
            args=(),
            params=ProcessRuntimeParams(stop_timeout=0.2),
        )
        await runtime.start()
        try:
            assert runtime.is_alive is True
        finally:
            await runtime.stop()
            assert runtime.is_alive is False

    @pytest.mark.anyio
    async def test_env_overrides_propagate_to_child(self):
        # ProcessRuntime updates the parent's `os.environ`; the child inherits.
        out_q: Queue = Queue()
        runtime = ProcessRuntime(
            target=_read_env_var,
            args=(out_q, "MINDOR_TEST_VAR"),
            params=ProcessRuntimeParams(env={"MINDOR_TEST_VAR": "from-params"}),
        )
        try:
            await runtime.start()
            assert out_q.get(timeout=5.0) == "from-params"
        finally:
            await runtime.stop()
            os.environ.pop("MINDOR_TEST_VAR", None)

    @pytest.mark.anyio
    async def test_stop_is_safe_before_start(self):
        runtime = ProcessRuntime(target=_exit_immediately, args=(), params=ProcessRuntimeParams())
        # Must not raise when the subprocess was never spawned.
        await runtime.stop()
