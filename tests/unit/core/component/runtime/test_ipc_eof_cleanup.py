"""Unit tests for IpcRuntimeProxy EOF cleanup.

`_handle_responses` must release every consumer parked on the manager when
the transport hits EOF (worker dies, container OOM, `docker kill`, etc.).
Without cleanup:
- `execute()` callers stay parked on their futures forever.
- Stream proxies stay parked on `state.queue.get()` forever.

These tests script a scenario where the transport returns `None` (EOF) and
verify the registered consumers are released with the right exceptions.
"""

from __future__ import annotations

import asyncio
from typing import List, Optional

import pytest

from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_message import IpcMessage, IpcMessageType
from mindor.core.component.runtime.base.ipc_stream import (
    IpcInboundStream,
    IpcStreamReader,
)
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec


@pytest.fixture
def anyio_backend():
    return "asyncio"


class _EofManager(IpcRuntimeProxy):
    """Manager whose transport is fed by a queue and can be told to EOF."""

    def __init__(self, worker_id: str = "eof-worker"):
        super().__init__(worker_id)
        self._start_timeout = 1.0
        self._stop_timeout = 1.0
        self._inbox: "asyncio.Queue[Optional[bytes]]" = asyncio.Queue()
        self.sent: List[bytes] = []

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
        self.sent.append(message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._inbox.get()

    def feed_eof(self) -> None:
        self._inbox.put_nowait(None)


def _register_pending_request(manager: _EofManager, request_id: str) -> asyncio.Future:
    """Mimic the bookkeeping done by `execute()` without spawning a worker."""
    future = manager._loop.create_future()
    manager._pending_requests[request_id] = future
    return future


def _handle_inbound_stream(manager: _EofManager, stream_id: str) -> IpcStreamReader:
    """Mimic the codec callback registering an inbound stream."""
    stream = IpcInboundStream(
        stream_id=stream_id,
        kind=StreamKind.BYTES,
        codec=VariableCodec(),
    )
    manager._inbound_streams[stream_id] = stream

    async def _noop_pull(_id: str) -> None: ...
    async def _noop_close(_id: str) -> None: ...

    return IpcStreamReader(stream, on_pull=_noop_pull, on_close=_noop_close)


@pytest.mark.anyio
async def test_eof_releases_pending_run_with_connection_error():
    manager = _EofManager()
    await manager.start()

    future_a = _register_pending_request(manager, "req-a")
    future_b = _register_pending_request(manager, "req-b")

    manager.feed_eof()

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(future_a, timeout=1.0)
    with pytest.raises(ConnectionError):
        await asyncio.wait_for(future_b, timeout=1.0)

    assert manager._pending_requests == {}
    await manager.stop()


@pytest.mark.anyio
async def test_eof_already_resolved_future_is_left_alone():
    """If a future already completed via RESULT before EOF arrives, the
    cleanup must not stomp on it. We resolve it first, then EOF."""
    manager = _EofManager()
    await manager.start()

    future = _register_pending_request(manager, "req-done")
    future.set_result({"output": 42})

    manager.feed_eof()
    # Give the response task a tick to consume the EOF.
    await asyncio.sleep(0.05)

    assert future.result() == {"output": 42}
    assert manager._pending_requests == {}
    await manager.stop()


@pytest.mark.anyio
async def test_eof_aborts_active_inbound_stream():
    """A consumer iterating an IpcStreamReader must see IOError when
    the worker dies mid-stream."""
    manager = _EofManager()
    await manager.start()

    reader = _handle_inbound_stream(manager, "stream-1")

    async def consume():
        with pytest.raises(IOError, match="stream-1"):
            async for _ in reader:
                pass

    consumer = asyncio.create_task(consume())
    # Let the consumer park on `queue.get()`.
    await asyncio.sleep(0.01)
    manager.feed_eof()

    await asyncio.wait_for(consumer, timeout=1.0)
    assert manager._inbound_streams == {}
    await manager.stop()


@pytest.mark.anyio
async def test_eof_releases_run_and_stream_together():
    """Realistic case: a RUN is in flight and produced an inbound stream
    before the container died. Both consumers must wake up."""
    manager = _EofManager()
    await manager.start()

    future = _register_pending_request(manager, "req-mixed")
    reader = _handle_inbound_stream(manager, "stream-mixed")

    async def consume_stream():
        with pytest.raises(IOError):
            async for _ in reader:
                pass

    consumer = asyncio.create_task(consume_stream())
    await asyncio.sleep(0.01)
    manager.feed_eof()

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(future, timeout=1.0)
    await asyncio.wait_for(consumer, timeout=1.0)
    await manager.stop()


@pytest.mark.anyio
async def test_explicit_abort_pending_on_eof_is_idempotent():
    """Calling the cleanup hook twice in a row must be a no-op the second
    time — useful when stop() and EOF race."""
    manager = _EofManager()
    await manager.start()

    future = _register_pending_request(manager, "req-x")
    manager._abort_pending_on_eof()
    manager._abort_pending_on_eof()  # no error

    with pytest.raises(ConnectionError):
        await asyncio.wait_for(future, timeout=1.0)
    await manager.stop()
