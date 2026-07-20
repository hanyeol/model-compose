"""Unit tests for IPC CANCEL propagation.

When the caller cancels an in-flight `IpcRuntimeProxy.request()`, the proxy
must send a CANCEL message to the worker so the remote task actually stops
instead of running to completion (and consuming resources for a result that
nobody is waiting for).

We wire a proxy + worker via in-memory queues (no subprocess) so we can:
- Verify CANCEL is emitted with the right request_id when the caller cancels.
- Verify the worker cancels the in-flight task upon receiving CANCEL.
- Verify unrelated in-flight requests are unaffected.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import pytest

from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ──────────────────────────────────────────────────────────────────────────────
# Test doubles — an in-memory duplex channel that both proxy & worker share.
# ──────────────────────────────────────────────────────────────────────────────


class _Channel:
    """Two asyncio.Queues playing the role of a bidirectional pipe."""

    def __init__(self):
        self.p2w: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()
        self.w2p: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()


class _MemProxy(IpcRuntimeProxy):
    def __init__(self, channel: _Channel, worker_id: str = "proxy"):
        super().__init__(worker_id)
        self._channel = channel
        self._start_timeout = 1.0
        self._stop_timeout = 1.0

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._response_task = asyncio.create_task(self._handle_responses())

    async def _stop(self) -> None:
        if self._response_task is not None:
            try:
                await asyncio.wait_for(self._response_task, timeout=1.0)
            except asyncio.TimeoutError:
                self._response_task.cancel()

    async def _send_message(self, message: bytes) -> None:
        await self._channel.p2w.put(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._channel.w2p.get()


class _MemWorker(IpcRuntimeWorker):
    """Worker whose `_execute_task` awaits a per-request event so tests can
    control when (if ever) it completes. Records what it observed."""

    def __init__(self, channel: _Channel, worker_id: str = "worker"):
        super().__init__(worker_id)
        self._channel = channel
        self.executed_inputs: List[Dict[str, Any]] = []
        self.cancelled_inputs: List[Dict[str, Any]] = []
        self.release_events: Dict[str, asyncio.Event] = {}

    def release_event(self, tag: str) -> asyncio.Event:
        event = self.release_events.get(tag)
        if event is None:
            event = asyncio.Event()
            self.release_events[tag] = event
        return event

    async def _start(self) -> None:
        return None

    async def _stop(self) -> None:
        return None

    async def _send_message(self, message: bytes) -> None:
        await self._channel.w2p.put(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._channel.p2w.get()

    def _close_transport(self) -> None:
        # Signal EOF back to the proxy so its response loop exits.
        self._channel.w2p.put_nowait(None)

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        self.executed_inputs.append(payload)
        try:
            await self.release_event(payload.get("tag", "")).wait()
        except asyncio.CancelledError:
            self.cancelled_inputs.append(payload)
            raise
        return { "echo": payload }


async def _spin_up(channel: _Channel):
    """Start proxy + worker as concurrent tasks and return handles."""
    proxy = _MemProxy(channel)
    worker = _MemWorker(channel)

    await proxy._start()
    worker_task = asyncio.create_task(worker.run())

    # Wait for the worker to publish STATUS=ready which the proxy discarded
    # in its own _wait_for_ready (we skipped that handshake here, so give the
    # loop a chance to bootstrap).
    await asyncio.sleep(0)

    return proxy, worker, worker_task


async def _tear_down(proxy: _MemProxy, worker: _MemWorker, worker_task: asyncio.Task):
    # Ask worker to stop and drain both sides.
    worker.running = False
    channel = proxy._channel
    channel.p2w.put_nowait(None)  # unblock worker's _recv if idle
    try:
        await asyncio.wait_for(worker_task, timeout=1.0)
    except asyncio.TimeoutError:
        worker_task.cancel()
    await proxy._stop()


# ──────────────────────────────────────────────────────────────────────────────
# Scenarios
# ──────────────────────────────────────────────────────────────────────────────


class TestIpcCancel:
    @pytest.mark.anyio
    async def test_proxy_sends_cancel_message_when_caller_cancels(self):
        """Cancelling the awaiter of `proxy.request()` must emit a CANCEL
        message with the same request_id over the transport."""
        channel = _Channel()
        proxy, worker, worker_task = await _spin_up(channel)

        try:
            # Kick off a request the worker will block on.
            req_task = asyncio.create_task(proxy.request({ "tag": "A" }))
            # Give the request time to leave the proxy and reach the worker.
            await asyncio.sleep(0.05)
            assert len(worker.executed_inputs) == 1
            original_request_id = list(proxy._pending_requests.keys())[0]

            req_task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await req_task

            # Worker should observe the CancelledError inside its handler.
            await asyncio.sleep(0.05)
            assert worker.cancelled_inputs == [{ "tag": "A" }]

            # The CANCEL message the proxy sent must reference the same
            # request_id as the original RUN.
            # (worker consumed messages from the queue; we can't inspect them
            # post-hoc — but observing worker.cancelled_inputs proves the
            # CANCEL was delivered and matched.)
            assert original_request_id not in proxy._pending_requests
        finally:
            await _tear_down(proxy, worker, worker_task)

    @pytest.mark.anyio
    async def test_cancel_does_not_affect_sibling_requests(self):
        """Cancelling one in-flight request must leave others running."""
        channel = _Channel()
        proxy, worker, worker_task = await _spin_up(channel)

        try:
            task_a = asyncio.create_task(proxy.request({ "tag": "A" }))
            task_b = asyncio.create_task(proxy.request({ "tag": "B" }))
            await asyncio.sleep(0.05)
            assert len(worker.executed_inputs) == 2

            task_a.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task_a

            # B is still running; release it and verify it completes normally.
            worker.release_event("B").set()
            result = await asyncio.wait_for(task_b, timeout=1.0)
            assert result == { "echo": { "tag": "B" } }
            assert worker.cancelled_inputs == [{ "tag": "A" }]
        finally:
            await _tear_down(proxy, worker, worker_task)

    @pytest.mark.anyio
    async def test_cancel_for_unknown_request_id_is_ignored(self):
        """A CANCEL for a request the worker never saw must be silently
        dropped — no crash, worker keeps serving."""
        channel = _Channel()
        proxy, worker, worker_task = await _spin_up(channel)

        try:
            # Manually push a CANCEL for a bogus request_id.
            bogus = IpcMessage(type=IpcMessageType.CANCEL, request_id="ghost").serialize()
            await channel.p2w.put(bogus)
            await asyncio.sleep(0.05)

            # Now issue a real request and complete it normally.
            task = asyncio.create_task(proxy.request({ "tag": "real" }))
            await asyncio.sleep(0.05)
            worker.release_event("real").set()
            result = await asyncio.wait_for(task, timeout=1.0)
            assert result == { "echo": { "tag": "real" } }
            assert worker.cancelled_inputs == []
        finally:
            await _tear_down(proxy, worker, worker_task)


class TestIpcMessageType:
    def test_cancel_is_a_valid_type(self):
        assert IpcMessageType.CANCEL.value == "cancel"

    def test_cancel_message_round_trips(self):
        msg = IpcMessage(type=IpcMessageType.CANCEL, request_id="req-1")
        data = msg.serialize()
        parsed = IpcMessage.deserialize(data)
        assert parsed.type == IpcMessageType.CANCEL.value
        assert parsed.request_id == "req-1"
