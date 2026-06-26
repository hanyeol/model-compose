"""Integration tests for IPC stream multiplexing in process runtime.

Covers the end-to-end flow defined in docs/specs/component-ipc.md:
- bytes inline (Tier B): bytes -> base64 marker -> bytes
- stream input (Tier C): BytesStreamResource flows from manager to worker,
  worker consumes chunks and reports the total length.
- stream output (Tier C): worker returns a BytesStreamResource, manager
  receives an async-iterable proxy and consumes chunks.

These tests use the real `ProcessRuntimeManager` + `ProcessRuntimeWorker` pair
with `multiprocessing.Process` + `multiprocessing.Queue` transport.
"""

import asyncio
from multiprocessing import Queue

import pytest

from mindor.core.foundation.runtime.process_manager import (
    ProcessRuntimeManager,
    ProcessRuntimeManagerParams,
)
from mindor.core.foundation.runtime.process_worker import ProcessRuntimeWorker
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.resources import StreamResource


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Worker definitions (module-level so they're picklable for spawn).
# ---------------------------------------------------------------------------

class EchoBytesWorker(ProcessRuntimeWorker):
    """Echo back the bytes payload received under input['data']."""
    async def _start(self):
        pass

    async def _stop(self):
        pass

    async def _execute_task(self, payload):
        data = payload["input"]["data"]
        assert isinstance(data, bytes), f"expected bytes, got {type(data).__name__}"
        return { "echoed": data }


class StreamInputWorker(ProcessRuntimeWorker):
    """Consume a streamed input and return statistics about it."""
    async def _start(self):
        pass

    async def _stop(self):
        pass

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


class StreamOutputWorker(ProcessRuntimeWorker):
    """Return a BytesStreamResource so the manager has to consume it."""
    async def _start(self):
        pass

    async def _stop(self):
        pass

    async def _execute_task(self, payload):
        size = payload["input"]["size"]
        chunk_size = payload["input"].get("chunk_size", 16)
        # Pattern: bytes 0..size-1 mod 256
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
    params = ProcessRuntimeManagerParams(start_timeout=10.0, stop_timeout=5.0)
    manager = ProcessRuntimeManager("echo-bytes", create_echo_bytes_worker, params)

    await manager.start()
    try:
        original = b"hello world\x00\xff\x10binary"
        result = await manager.execute({
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
    params = ProcessRuntimeManagerParams(start_timeout=10.0, stop_timeout=5.0)
    manager = ProcessRuntimeManager("stream-input", create_stream_input_worker, params)

    await manager.start()
    try:
        # 100 bytes split into 16-byte chunks (last chunk smaller)
        original = bytes(range(100))
        stream = BytesStreamResource(original, chunk_size=16)

        result = await manager.execute({
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
    params = ProcessRuntimeManagerParams(start_timeout=10.0, stop_timeout=5.0)
    manager = ProcessRuntimeManager("stream-output", create_stream_output_worker, params)

    await manager.start()
    try:
        result = await manager.execute({
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
