"""Integration tests for IPC stream multiplexing in process runtime.

Covers the end-to-end flow defined in docs/specs/component-ipc.md:
- bytes inline (Tier B): bytes -> base64 marker -> bytes
- stream input (Tier C): BytesStreamResource flows from manager to worker,
  worker consumes chunks and reports the total length.
- stream output (Tier C): worker returns a BytesStreamResource, manager
  receives an async-iterable proxy and consumes chunks.

These tests use the IPC base (`IpcRuntimeProxy` + `IpcRuntimeWorker`)
composed with `ProcessRuntime` lifecycle and `multiprocessing.Queue` transport.
"""

import asyncio
from multiprocessing import Queue
from typing import Any, Dict, Optional

import pytest

from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.runtime.process import ProcessRuntime, ProcessRuntimeParams


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Minimal Queue-based IPC base for the tests.
# ---------------------------------------------------------------------------

class QueueIpcWorker(IpcRuntimeWorker):
    """Test scaffold: an IpcRuntimeWorker that talks over two Queues."""

    def __init__(self, worker_id: str, request_queue: Queue, response_queue: Queue):
        super().__init__(worker_id)
        self.request_queue = request_queue
        self.response_queue = response_queue

    async def _send_message(self, message: bytes) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.response_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.request_queue.get)

    def _close_transport(self) -> None:
        pass


class QueueIpcManager(IpcRuntimeProxy):
    """Test scaffold: an IpcRuntimeProxy that owns two Queues and a
    `ProcessRuntime` lifecycle.
    """

    def __init__(self, worker_id: str, worker_factory, params: ProcessRuntimeParams):
        super().__init__(worker_id)
        self._start_timeout = params.start_timeout
        self._stop_timeout = params.stop_timeout

        self._request_queue: Queue = Queue()
        self._response_queue: Queue = Queue()
        self._runtime = ProcessRuntime(
            target=_run_worker,
            args=(worker_factory, worker_id, self._request_queue, self._response_queue),
            params=params,
        )

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._runtime.start()
        await self._wait_for_ready()
        self._response_task = asyncio.create_task(self._handle_responses())

    async def stop(self) -> None:
        await self._send_stop_message()
        await self._runtime.stop()
        if self._response_queue is not None:
            self._response_queue.put(None)
        if self._response_task is not None:
            try:
                await self._response_task
            except asyncio.CancelledError:
                pass

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._request_queue.put, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._response_queue.get)


def _run_worker(worker_factory, worker_id, request_queue, response_queue) -> None:
    worker = worker_factory(worker_id, request_queue, response_queue)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(worker.run())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# Worker implementations (module-level so they're picklable for spawn).
# ---------------------------------------------------------------------------

class EchoBytesWorker(QueueIpcWorker):
    """Echo back the bytes payload received under input['data']."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        data = payload["input"]["data"]
        assert isinstance(data, bytes), f"expected bytes, got {type(data).__name__}"
        return { "echoed": data }


class StreamInputWorker(QueueIpcWorker):
    """Consume a streamed input and return statistics about it."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        stream = payload["input"]["stream"]
        assert isinstance(stream, StreamResource), (
            f"expected StreamResource, got {type(stream).__name__}"
        )
        total = 0
        chunks = 0
        async for chunk in stream:
            total += len(chunk)
            chunks += 1
        return { "total_bytes": total, "chunks": chunks }


class StreamOutputWorker(QueueIpcWorker):
    """Return a BytesStreamResource so the manager has to consume it."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        size = payload["input"]["size"]
        chunk_size = payload["input"].get("chunk_size", 16)
        data = bytes((i & 0xFF) for i in range(size))
        return { "stream": BytesStreamResource(data, chunk_size=chunk_size) }


def create_echo_bytes_worker(worker_id, req_queue, res_queue):
    return EchoBytesWorker(worker_id, req_queue, res_queue)


def create_stream_input_worker(worker_id, req_queue, res_queue):
    return StreamInputWorker(worker_id, req_queue, res_queue)


def create_stream_output_worker(worker_id, req_queue, res_queue):
    return StreamOutputWorker(worker_id, req_queue, res_queue)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_inline_bytes_roundtrip():
    """Tier B: bytes payload survives base64 marker round-trip."""
    params = ProcessRuntimeParams(start_timeout=10.0, stop_timeout=5.0)
    manager = QueueIpcManager("echo-bytes", create_echo_bytes_worker, params)

    await manager.start()
    try:
        original = b"hello world\x00\xff\x10binary"
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": { "data": original },
        })
        assert result == { "echoed": original }
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_stream_input_roundtrip():
    """Tier C input: BytesStreamResource is encoded as a stream marker,
    chunks flow manager -> worker via STREAM_PULL/CHUNK/END, worker
    consumes the proxy and reports the totals."""
    params = ProcessRuntimeParams(start_timeout=10.0, stop_timeout=5.0)
    manager = QueueIpcManager("stream-input", create_stream_input_worker, params)

    await manager.start()
    try:
        original = bytes(range(100))
        stream = BytesStreamResource(original, chunk_size=16)

        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": { "stream": stream },
        })
        assert result["total_bytes"] == 100
        # 100 / 16 = 6 full chunks (96 bytes) + 1 partial (4 bytes) = 7
        assert result["chunks"] == 7
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_stream_output_roundtrip():
    """Tier C output: worker returns a BytesStreamResource, manager receives
    an async-iterable proxy and consumes chunks via STREAM_PULL/CHUNK/END."""
    params = ProcessRuntimeParams(start_timeout=10.0, stop_timeout=5.0)
    manager = QueueIpcManager("stream-output", create_stream_output_worker, params)

    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": { "size": 100, "chunk_size": 16 },
        })

        stream = result["stream"]
        assert isinstance(stream, StreamResource), (
            f"expected StreamResource, got {type(stream).__name__}"
        )

        received = bytearray()
        chunks = 0
        async for chunk in stream:
            received.extend(chunk)
            chunks += 1

        expected = bytes((i & 0xFF) for i in range(100))
        assert bytes(received) == expected
        assert chunks == 7
    finally:
        await manager.stop()
