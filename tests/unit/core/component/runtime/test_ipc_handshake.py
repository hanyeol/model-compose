"""Unit tests for the IPC start-up handshake.

Covers `IpcRuntimeProxy._wait_for_ready` failure paths that the
integration tests can't easily reach:

- worker pushes STATUS=ready → returns cleanly.
- worker pushes ERROR before READY → `RuntimeError` with payload message.
- worker EOFs (recv returns None) before READY → `RuntimeError`.
- worker never publishes anything within the start_timeout → `TimeoutError`.
- worker pushes a non-ready STATUS first, then ready → still succeeds.

These tests build a minimal in-memory `IpcRuntimeProxy` subclass whose
`_recv_message` is fed by an `asyncio.Queue`, so we can simulate each
handshake outcome deterministically without spawning a subprocess.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _ScriptedManager(IpcRuntimeProxy):
    """In-memory manager: `_recv_message` returns the next scripted bytes
    (or blocks forever once exhausted)."""

    def __init__(self, worker_id: str, start_timeout: float = 1.0):
        super().__init__(worker_id)
        self._start_timeout = start_timeout
        self._stop_timeout = 1.0
        self._inbox: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()
        self.sent: List[bytes] = []

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()

    async def _stop(self) -> None:
        return None

    async def _send_message(self, message: bytes) -> None:
        self.sent.append(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._inbox.get()

    def feed(self, message: Optional[IpcMessage]) -> None:
        """Push the next message that `_recv_message` should return. Pass
        `None` to simulate EOF (recv returns None)."""
        if message is None:
            self._inbox.put_nowait(None)
        else:
            self._inbox.put_nowait(message.serialize())


class TestWaitForReady:
    @pytest.mark.anyio
    async def test_returns_on_status_ready(self):
        manager = _ScriptedManager("ok-worker")
        await manager.start()
        manager.feed(IpcMessage(
            type=IpcMessageType.STATUS,
            payload={"status": "ready"},
        ))
        # No exception, no timeout.
        await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_error_message_before_ready_raises_runtime_error(self):
        manager = _ScriptedManager("erroring-worker")
        await manager.start()
        manager.feed(IpcMessage(
            type=IpcMessageType.ERROR,
            payload={"error": "boom from worker"},
        ))
        with pytest.raises(RuntimeError, match="boom from worker"):
            await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_error_without_payload_uses_default_message(self):
        manager = _ScriptedManager("erroring-worker")
        await manager.start()
        manager.feed(IpcMessage(type=IpcMessageType.ERROR, payload={}))
        with pytest.raises(RuntimeError, match="Unknown error"):
            await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_eof_before_ready_raises_runtime_error(self):
        manager = _ScriptedManager("dying-worker")
        await manager.start()
        manager.feed(None)  # recv returns None → EOF
        with pytest.raises(RuntimeError, match="exited before becoming ready"):
            await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_timeout_when_worker_silent(self):
        manager = _ScriptedManager("silent-worker", start_timeout=0.05)
        await manager.start()
        # Never feed anything; wait_for_ready must time out.
        with pytest.raises(TimeoutError, match="did not start within"):
            await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_non_ready_status_is_ignored_then_ready_succeeds(self):
        """Per the implementation, STATUS messages whose `status` is not
        'ready' are skipped (e.g., 'starting'), and the loop keeps waiting."""
        manager = _ScriptedManager("two-step-worker", start_timeout=1.0)
        await manager.start()
        manager.feed(IpcMessage(type=IpcMessageType.STATUS, payload={"status": "starting"}))
        manager.feed(IpcMessage(type=IpcMessageType.STATUS, payload={"status": "ready"}))
        await manager._wait_for_ready()

    @pytest.mark.anyio
    async def test_unrelated_messages_are_skipped(self):
        """RESULT/LOG/HEARTBEAT arriving before STATUS=ready should be
        ignored — only ERROR or STATUS=ready terminate the loop."""
        manager = _ScriptedManager("noisy-worker", start_timeout=1.0)
        await manager.start()
        manager.feed(IpcMessage(type=IpcMessageType.LOG, payload={"line": "starting up"}))
        manager.feed(IpcMessage(type=IpcMessageType.HEARTBEAT))
        manager.feed(IpcMessage(type=IpcMessageType.STATUS, payload={"status": "ready"}))
        await manager._wait_for_ready()
