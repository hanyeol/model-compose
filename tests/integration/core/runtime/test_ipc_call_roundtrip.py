"""Integration tests for reverse-direction CALL messages.

These exercise the stage-1 contract laid out in the encoder-split design:
a worker running under `IpcRuntimeWorker` can issue a CALL back to the parent
process, which dispatches via `IpcRuntimeProxy.on_call` and returns a result
or error. CALL_CANCEL from the worker aborts the parent-side task.

Tensor payloads are covered as an in-process codec round-trip — the wire path
is identical to any other `__variable__` marker, so testing it via the codec
plus a one-call CALL round-trip is enough to prove the shape.
"""

import asyncio
from multiprocessing import Queue
from typing import Any, Dict, Optional

import pytest

from mindor.core.foundation.runtime.ipc_proxy import IpcRuntimeProxy
from mindor.core.foundation.runtime.ipc_worker import IpcRuntimeWorker
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.resources import AsyncIterableStreamResource, StreamResource
from mindor.core.foundation.variable.codec import VariableCodec
from mindor.core.foundation.variable.time import parse_time
from mindor.core.runtime.process import ProcessRuntime
from mindor.dsl.schema.runtime import ProcessRuntimeConfig
from mindor.dsl.schema.runtime.impl.types import RuntimeType


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
    def __init__(self, worker_id: str, worker_factory, config: ProcessRuntimeConfig):
        super().__init__(worker_id)
        self._start_timeout = parse_time(config.start_timeout)
        self._stop_timeout = parse_time(config.stop_timeout)

        self._request_queue: Queue = Queue()
        self._response_queue: Queue = Queue()
        self._runtime = ProcessRuntime(
            target=_run_worker,
            args=(worker_factory, worker_id, self._request_queue, self._response_queue),
            config=config,
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
# Worker implementations. Each RUN turns around and issues a CALL back to the
# parent so one RUN result reflects the CALL's success/failure/cancellation.
# ---------------------------------------------------------------------------

class CallEchoWorker(QueueIpcWorker):
    """Issues one CALL per RUN, forwarding the RUN input into the CALL payload."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        reply = await self.call(payload["input"])
        return { "reply": reply }


class CallExpectErrorWorker(QueueIpcWorker):
    """Issues a CALL and expects it to raise — captures the error message."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        try:
            await self.call(payload["input"])
        except Exception as e:
            return { "caught": str(e)[:200] }
        return { "caught": None }


class CallCancellableWorker(QueueIpcWorker):
    """Issues a CALL and cancels it after a short delay so the parent sees CALL_CANCEL."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        call_task = asyncio.create_task(self.call(payload["input"]))
        # Give the parent long enough to start its slow handler before we cancel.
        await asyncio.sleep(0.2)
        call_task.cancel()
        try:
            await call_task
        except asyncio.CancelledError:
            return { "cancelled": True }
        except Exception as e:
            return { "cancelled": False, "error": str(e)[:200] }
        return { "cancelled": False }


def create_call_echo_worker(worker_id, req_queue, res_queue):
    return CallEchoWorker(worker_id, req_queue, res_queue)


def create_call_expect_error_worker(worker_id, req_queue, res_queue):
    return CallExpectErrorWorker(worker_id, req_queue, res_queue)


def create_call_cancellable_worker(worker_id, req_queue, res_queue):
    return CallCancellableWorker(worker_id, req_queue, res_queue)


# ---------------------------------------------------------------------------
# Reverse-direction stream workers.
# ---------------------------------------------------------------------------

class CallStreamInputWorker(QueueIpcWorker):
    """Issues one CALL whose payload is a worker-produced byte stream."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        size = payload["input"]["size"]
        chunk_size = payload["input"].get("chunk_size", 16)
        data = bytes((i & 0xFF) for i in range(size))
        reply = await self.call({
            "stream": BytesStreamResource(data, chunk_size=chunk_size),
        })
        return { "reply": reply }


class CallStreamOutputWorker(QueueIpcWorker):
    """Issues a CALL and expects a stream in the reply — consumes it and reports totals."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        reply = await self.call(payload["input"])
        stream = reply["stream"]
        if not isinstance(stream, StreamResource):
            return { "ok": False, "reason": f"expected StreamResource, got {type(stream).__name__}" }
        total = 0
        chunks = 0
        async for chunk in stream:
            total += len(chunk)
            chunks += 1
        return { "total_bytes": total, "chunks": chunks }


class CallCancelWhileStreamingWorker(QueueIpcWorker):
    """Issues a CALL expecting a stream reply, starts consuming, then cancels mid-flight."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        reply_box = {}

        async def consume():
            reply = await self.call({})
            reply_box["stream"] = reply["stream"]
            received = 0
            async for chunk in reply["stream"]:
                received += len(chunk)
            reply_box["received"] = received

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.15)  # let a chunk or two flow
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            return { "cancelled": True, "received": reply_box.get("received", -1) }
        return { "cancelled": False }


def create_call_stream_input_worker(worker_id, req_queue, res_queue):
    return CallStreamInputWorker(worker_id, req_queue, res_queue)


def create_call_stream_output_worker(worker_id, req_queue, res_queue):
    return CallStreamOutputWorker(worker_id, req_queue, res_queue)


def create_call_cancel_while_streaming_worker(worker_id, req_queue, res_queue):
    return CallCancelWhileStreamingWorker(worker_id, req_queue, res_queue)


# ---------------------------------------------------------------------------
# CALL round-trip tests.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_call_result_roundtrip():
    """Worker CALL -> parent on_call handler -> CALL_RESULT -> worker sees reply."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-echo", create_call_echo_worker, config)

    seen_payloads = []

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        seen_payloads.append(payload)
        return { "sum": payload["a"] + payload["b"], "note": payload.get("note") }

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     { "a": 2, "b": 3, "note": "hello" },
        })
        assert result == { "reply": { "sum": 5, "note": "hello" } }
        assert seen_payloads == [{ "a": 2, "b": 3, "note": "hello" }]
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_call_error_propagates_to_worker():
    """Parent handler raises -> CALL_ERROR -> worker's `call()` raises."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-error", create_call_expect_error_worker, config)

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        raise RuntimeError("intentional failure in parent handler")

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     {},
        })
        assert result["caught"] is not None
        assert "intentional failure in parent handler" in result["caught"]
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_call_missing_handler_errors():
    """No on_call registered -> CALL_ERROR -> worker's `call()` raises."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-no-handler", create_call_expect_error_worker, config)

    # Intentionally leave manager.on_call = None.
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     {},
        })
        assert result["caught"] is not None
        assert "no CALL handler" in result["caught"]
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_call_cancel_aborts_parent_handler():
    """Worker cancels its CALL -> CALL_CANCEL -> parent task is cancelled."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-cancel", create_call_cancellable_worker, config)

    handler_cancelled = asyncio.Event()

    async def slow_handler(call_id: str, payload: Dict[str, Any]) -> Any:
        try:
            await asyncio.sleep(10.0)
        except asyncio.CancelledError:
            handler_cancelled.set()
            raise
        return { "unreachable": True }

    manager.on_call = slow_handler
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     {},
        })
        assert result == { "cancelled": True }
        # The parent-side handler must observe the cancellation, not just return early.
        assert handler_cancelled.is_set()
    finally:
        await manager.stop()


# ---------------------------------------------------------------------------
# Tensor codec round-trip. In-process: VariableCodec is the whole wire path
# for inline variables.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_tensor_codec_roundtrip_bfloat16():
    import torch

    original = torch.arange(12, dtype=torch.float32).reshape(3, 4).to(torch.bfloat16)

    codec = VariableCodec()
    wire = codec.encode({ "t": original })
    assert isinstance(wire, dict) and "t" in wire
    marker = wire["t"]["__variable__"]
    assert marker["type"] == "tensor"
    assert isinstance(marker["value"], str) and marker["value"]

    decoded = codec.decode(wire)
    restored = decoded["t"]
    assert restored.dtype == torch.bfloat16
    assert restored.shape == (3, 4)
    assert torch.equal(restored, original)


@pytest.mark.anyio
async def test_tensor_codec_roundtrip_nested_in_dict():
    import torch

    payload = {
        "label": "hidden_states",
        "state": torch.ones(2, 2, dtype=torch.float16),
        "meta":  { "layer": 50, "token_types": ["text", "text"] },
    }

    codec = VariableCodec()
    wire = codec.encode(payload)
    decoded = codec.decode(wire)

    assert decoded["label"] == "hidden_states"
    assert decoded["meta"] == { "layer": 50, "token_types": ["text", "text"] }
    assert torch.equal(decoded["state"], payload["state"])
    assert decoded["state"].dtype == torch.float16


# ---------------------------------------------------------------------------
# Reverse-direction stream tests.
#
# These prove the symmetric STREAM_* wire path works when the stream variable
# travels inside a CALL payload or CALL_RESULT. They also prove that cancelling
# a CALL mid-stream propagates STREAM_ABORT via the owner-sweep.
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_call_payload_carries_stream():
    """Worker puts a BytesStreamResource into CALL payload; parent handler consumes."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-stream-in", create_call_stream_input_worker, config)

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        stream = payload["stream"]
        assert isinstance(stream, StreamResource), type(stream).__name__
        total = 0
        chunks = 0
        async for chunk in stream:
            total += len(chunk)
            chunks += 1
        return { "total_bytes": total, "chunks": chunks }

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     { "size": 100, "chunk_size": 16 },
        })
        # 100 / 16 = 6 full + 1 partial = 7 chunks.
        assert result == { "reply": { "total_bytes": 100, "chunks": 7 } }
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_call_result_carries_stream():
    """Parent handler returns a BytesStreamResource; worker consumes it."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-stream-out", create_call_stream_output_worker, config)

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        size = payload["size"]
        chunk_size = payload.get("chunk_size", 16)
        data = bytes((i & 0xFF) for i in range(size))
        return { "stream": BytesStreamResource(data, chunk_size=chunk_size) }

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     { "size": 100, "chunk_size": 16 },
        })
        assert result == { "total_bytes": 100, "chunks": 7 }
    finally:
        await manager.stop()


@pytest.mark.anyio
async def test_call_cancel_sweeps_worker_outbound_stream():
    """Worker CALLs with an outbound stream in the payload, cancels the call
    while the parent handler is still consuming. The worker's cancel path
    must abort its registered outbound stream (owner sweep) so the parent
    reader sees STREAM_ABORT instead of hanging on the next pull."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("call-sweep", create_call_cancel_outbound_worker, config)

    stream_errored = asyncio.Event()
    chunks_seen = 0

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        stream = payload["stream"]
        nonlocal chunks_seen
        try:
            async for chunk in stream:
                chunks_seen += 1
                # Sleep so the worker has time to cancel while we're mid-iteration.
                await asyncio.sleep(0.05)
        except BaseException:
            # CALL_CANCEL cancels the handler task; STREAM_ABORT surfaces as
            # IOError inside the reader. We don't care which arrived first —
            # the point is iteration terminates (not hangs).
            stream_errored.set()
            raise
        return { "unreachable": True }

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     {},
        })
        assert result == { "cancelled": True }
        # The parent handler's iteration must have been broken by STREAM_ABORT.
        await asyncio.wait_for(stream_errored.wait(), timeout=2.0)
        # And we cancelled before all 100 chunks drained.
        assert chunks_seen < 100
    finally:
        await manager.stop()


class CallCancelOutboundStreamWorker(QueueIpcWorker):
    """Issues a CALL whose payload is a worker-produced stream, then cancels mid-flight."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        async def source():
            for i in range(100):
                await asyncio.sleep(0.02)
                yield bytes([i & 0xFF]) * 8

        call_task = asyncio.create_task(self.call({
            "stream": AsyncIterableStreamResource(source(), content_type="application/octet-stream"),
        }))
        await asyncio.sleep(0.2)  # let parent consume a few chunks
        call_task.cancel()
        try:
            await call_task
        except asyncio.CancelledError:
            return { "cancelled": True }
        return { "cancelled": False }


def create_call_cancel_outbound_worker(worker_id, req_queue, res_queue):
    return CallCancelOutboundStreamWorker(worker_id, req_queue, res_queue)


# ---------------------------------------------------------------------------
# Slow-generator cleanup: owner-sweep must tear down the source iterator so
# its `finally` runs, even if the generator is parked in `await` at the
# moment of cancel.
# ---------------------------------------------------------------------------

class BreakMidStreamWorker(QueueIpcWorker):
    """Consumes a CALL-reply stream briefly then `break`s out — no explicit
    close, no `aclose()`. The reader's async-generator finally must still
    fire and send STREAM_CLOSE automatically."""
    async def _start(self): pass
    async def _stop(self): pass

    async def _execute_task(self, payload, on_event=None):
        reply = await self.call({})
        received = 0
        async for chunk in reply["stream"]:
            received += len(chunk)
            if received >= 8:
                break  # no explicit aclose — generator cleanup must handle it
        return { "received": received }


def create_break_mid_stream_worker(worker_id, req_queue, res_queue):
    return BreakMidStreamWorker(worker_id, req_queue, res_queue)


@pytest.mark.anyio
async def test_break_on_reader_sends_stream_close_and_runs_source_finally():
    """Worker uses plain `async for ... break` with no `.close()`. The reader
    is an async generator with a `try/finally`, so Python's async-generator
    cleanup auto-sends STREAM_CLOSE on scope exit. The parent then cancels
    its pump and acloses the source iterator — its `finally` runs promptly."""
    config = ProcessRuntimeConfig(type=RuntimeType.PROCESS, start_timeout="10s", stop_timeout="5s")
    manager = QueueIpcManager("break-stream-finally", create_break_mid_stream_worker, config)

    source_finally_ran = asyncio.Event()

    async def slow_source():
        try:
            for i in range(1000):
                await asyncio.sleep(0.1)
                yield b"\xaa" * 8
        finally:
            source_finally_ran.set()

    async def handle(call_id: str, payload: Dict[str, Any]) -> Any:
        return {
            "stream": AsyncIterableStreamResource(
                slow_source(),
                content_type="application/octet-stream",
            ),
        }

    manager.on_call = handle
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id":    "r1",
            "input":     {},
        })
        assert result["received"] >= 1
        # Would take ~100 s if the generator were left parked.
        await asyncio.wait_for(source_finally_ran.wait(), timeout=2.0)
    finally:
        await manager.stop()
