"""Edge-case integration tests for IPC stream multiplexing.

Companion to `test_ipc_stream_roundtrip.py` which covers the BYTES happy path.
This file targets the streaming-error / non-bytes-kind paths the existing
integration suite missed:

- TEXT-kind streams (manager → worker, worker → manager) via
  `StreamEncodingIterator(format=TEXT)`.
- OBJECT-kind streams via `StreamEncodingIterator(format=JSON)` carrying
  JSON-serializable dicts.
- Producer-side abort: the worker yields a stream that raises mid-iteration;
  the manager must see the abort propagated as an `IOError` from the proxy.
- Multi-chunk credit=1 ordering: a large source split across many chunks
  must arrive in seq order.
- Consumer-side close: the manager returns from `execute()` without
  consuming the output stream; the worker must observe STREAM_CLOSE and
  drop its outbound state.

These share the `QueueIpcManager` / `QueueIpcWorker` scaffolding pattern
from `test_ipc_stream_roundtrip.py` (duplicated here so the two files can
evolve independently — the scaffolding is small).
"""

from __future__ import annotations

import asyncio
from multiprocessing import Queue
from typing import Any, AsyncIterator, Optional

import pytest

from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.iterators import (
    StreamEncodingFormat,
    StreamEncodingIterator,
    StreamChunkIterator,
)
from mindor.core.runtime.process import ProcessRuntime, ProcessRuntimeParams


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Queue-based IPC scaffolding (mirrors test_ipc_stream_roundtrip.py).
# ---------------------------------------------------------------------------

class QueueIpcWorker(IpcRuntimeWorker):
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

    async def _start(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._runtime.start()
        await self._wait_for_ready()
        self._response_task = asyncio.create_task(self._handle_responses())

    async def _stop(self) -> None:
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
# Module-level worker classes (picklable for `spawn`).
# ---------------------------------------------------------------------------

class TextStreamInputWorker(QueueIpcWorker):
    """Consume a TEXT-kind stream and report the concatenated string."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        stream = payload["input"]["stream"]
        # TEXT-kind streams resolve to a StreamChunkIterator (no MIME match).
        chunks = []
        async for piece in stream:
            chunks.append(piece)
        return {
            "joined": "".join(chunks),
            "count": len(chunks),
        }


class TextStreamOutputWorker(QueueIpcWorker):
    """Return a TEXT-kind stream via StreamEncodingIterator(format=TEXT)."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        pieces = payload["input"]["pieces"]

        async def gen() -> AsyncIterator[str]:
            for piece in pieces:
                yield piece

        return {"stream": StreamEncodingIterator(gen(), format=StreamEncodingFormat.TEXT)}


class ObjectStreamOutputWorker(QueueIpcWorker):
    """Return an OBJECT-kind stream of JSON-serializable dicts."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        items = payload["input"]["items"]

        async def gen() -> AsyncIterator[Any]:
            for item in items:
                yield item

        return {"stream": StreamEncodingIterator(gen(), format=StreamEncodingFormat.JSON)}


class AbortingOutputWorker(QueueIpcWorker):
    """Return a stream whose producer raises after `fail_after` chunks."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        fail_after = payload["input"]["fail_after"]
        message = payload["input"]["message"]

        async def gen() -> AsyncIterator[str]:
            for i in range(fail_after):
                yield f"chunk-{i}"
            raise RuntimeError(message)

        return {"stream": StreamEncodingIterator(gen(), format=StreamEncodingFormat.TEXT)}


class LargeBytesOutputWorker(QueueIpcWorker):
    """Return a BYTES stream that produces many small chunks — exercises
    credit=1 ordering across a higher chunk count than the happy-path test."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        size = payload["input"]["size"]
        chunk_size = payload["input"]["chunk_size"]
        data = bytes((i & 0xFF) for i in range(size))
        return {"stream": BytesStreamResource(data, chunk_size=chunk_size)}


class StreamOutputForCloseWorker(QueueIpcWorker):
    """Return a long-running stream so the manager can close it early.

    The generator pauses between chunks so that, in practice, the manager
    can issue STREAM_CLOSE before the producer reaches the end.
    """
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload):
        async def gen() -> AsyncIterator[str]:
            for i in range(1000):
                await asyncio.sleep(0.005)
                yield f"piece-{i}"

        return {"stream": StreamEncodingIterator(gen(), format=StreamEncodingFormat.TEXT)}


def _create_text_input(worker_id, req_q, res_q):
    return TextStreamInputWorker(worker_id, req_q, res_q)


def _create_text_output(worker_id, req_q, res_q):
    return TextStreamOutputWorker(worker_id, req_q, res_q)


def _create_object_output(worker_id, req_q, res_q):
    return ObjectStreamOutputWorker(worker_id, req_q, res_q)


def _create_aborting_output(worker_id, req_q, res_q):
    return AbortingOutputWorker(worker_id, req_q, res_q)


def _create_large_bytes_output(worker_id, req_q, res_q):
    return LargeBytesOutputWorker(worker_id, req_q, res_q)


def _create_close_output(worker_id, req_q, res_q):
    return StreamOutputForCloseWorker(worker_id, req_q, res_q)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

PARAMS = ProcessRuntimeParams(start_timeout=15.0, stop_timeout=5.0)


@pytest.mark.anyio
async def test_text_stream_input_roundtrip():
    """TEXT-kind input: manager sends an StreamEncodingIterator(format=TEXT);
    chunks travel as raw str on the wire and worker concatenates them."""
    manager = QueueIpcManager("text-input", _create_text_input, PARAMS)
    await manager.start()
    try:
        pieces = ["alpha-", "beta-", "gamma-", "δέλτα"]

        async def gen() -> AsyncIterator[str]:
            for piece in pieces:
                yield piece

        stream = StreamEncodingIterator(gen(), format=StreamEncodingFormat.TEXT)

        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"stream": stream},
        })

        assert result == {"joined": "".join(pieces), "count": len(pieces)}
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_text_stream_output_roundtrip():
    """TEXT-kind output: worker returns StreamEncodingIterator(format=TEXT);
    manager receives a StreamChunkIterator yielding str values."""
    manager = QueueIpcManager("text-output", _create_text_output, PARAMS)
    await manager.start()
    try:
        pieces = ["one", "two", "three"]
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"pieces": pieces},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamChunkIterator)

        received = [chunk async for chunk in stream]
        assert received == pieces
        for chunk in received:
            assert isinstance(chunk, str)
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_object_stream_output_roundtrip():
    """OBJECT-kind output: each chunk is a JSON-serializable dict.

    `StreamEncodingIterator(format=JSON)` serializes via json.dumps so the wire
    payload arrives as a string; the consumer sees those raw strings (the
    OBJECT kind passes wire data through unchanged when there's no codec
    transformation registered)."""
    manager = QueueIpcManager("object-output", _create_object_output, PARAMS)
    await manager.start()
    try:
        items = [
            {"event": "start", "i": 0},
            {"event": "data", "i": 1, "payload": [1, 2, 3]},
            {"event": "end", "i": 2},
        ]
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"items": items},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamChunkIterator)

        received = [chunk async for chunk in stream]
        # StreamEncodingIterator(format=JSON) emits JSON strings; the OBJECT
        # kind preserves them verbatim through the IPC wire.
        import json
        assert [json.loads(s) for s in received] == items
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_output_stream_abort_propagates_as_ioerror():
    """Producer raises mid-stream → worker emits STREAM_ABORT →
    consumer proxy raises IOError on the next __anext__."""
    manager = QueueIpcManager("abort-output", _create_aborting_output, PARAMS)
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"fail_after": 3, "message": "boom"},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamChunkIterator)

        received = []
        with pytest.raises(IOError, match="aborted"):
            async for piece in stream:
                received.append(piece)

        # The three pre-abort chunks must have arrived before the failure.
        assert received == ["chunk-0", "chunk-1", "chunk-2"]
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_large_bytes_stream_preserves_order_across_many_chunks():
    """Credit=1 ordering: 1 KiB split into 32-byte chunks (32 chunks)
    must arrive in seq order with full data integrity."""
    manager = QueueIpcManager("large-bytes", _create_large_bytes_output, PARAMS)
    await manager.start()
    try:
        size = 1024
        chunk_size = 32
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"size": size, "chunk_size": chunk_size},
        })

        stream = result["stream"]
        received = bytearray()
        chunks = 0
        async for chunk in stream:
            received.extend(chunk)
            chunks += 1

        expected = bytes((i & 0xFF) for i in range(size))
        assert bytes(received) == expected
        assert chunks == size // chunk_size
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_consumer_close_releases_worker_outbound_stream():
    """Manager calls aclose() on the proxy after a few chunks → worker
    receives STREAM_CLOSE → worker drops its outbound state.

    We can't directly inspect the child process's `_outbound_streams`, but
    we *can* verify that closing early does not hang the manager and that
    a follow-up RUN on the same manager still completes normally — which
    would deadlock if the previous stream's pump never released."""
    manager = QueueIpcManager("close-output", _create_close_output, PARAMS)
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamChunkIterator)

        # Consume a handful of chunks then bail out via aclose().
        received = []
        it = stream.__aiter__()
        for _ in range(5):
            received.append(await it.__anext__())
        assert received == [f"piece-{i}" for i in range(5)]

        # aclose() on the underlying async-generator emits STREAM_CLOSE.
        await it.aclose()

        # The manager must still accept follow-up work — proves the
        # response loop wasn't wedged by the dangling stream.
        result2 = await manager.request({
            "action_id": "noop",
            "run_id": "r2",
            "input": {},
        })
        # Just drain one chunk to confirm the second stream is alive.
        second_stream = result2["stream"]
        first_chunk = await second_stream.__aiter__().__anext__()
        assert first_chunk == "piece-0"
    finally:
        await manager.stop()
