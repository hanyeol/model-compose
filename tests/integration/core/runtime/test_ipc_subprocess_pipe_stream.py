"""Integration test: IpcRuntimeProxy + IpcRuntimeWorker over a real
`SubprocessPipeChannel`.

The existing roundtrip suite (test_ipc_stream_roundtrip.py) talks over
`multiprocessing.Queue`. The venv runtime instead talks over OS pipes via
`SubprocessPipeChannel`, and that transport had no end-to-end stream test —
this file fills that gap.

We run the worker in a background thread (with its own asyncio loop) so the
manager and worker can communicate through a real fd-pair channel inside a
single test process. This exercises:

- IPC framing through `SubprocessPipeChannel.send`/`recv` (line-framed bytes).
- The full STREAM_PULL/CHUNK/END credit-1 protocol over that transport.
- A bytes-stream output (worker → manager) and an inline RUN payload.
"""

from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Dict, Optional

import pytest

from mindor.core.component.runtime.base.ipc_proxy import IpcRuntimeProxy
from mindor.core.component.runtime.base.ipc_worker import IpcRuntimeWorker
from mindor.core.foundation.streaming.bytes import BytesStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.utils.channels.subprocess_pipe import SubprocessPipeChannel


@pytest.fixture
def anyio_backend():
    return "asyncio"


# ---------------------------------------------------------------------------
# Channel-backed Manager / Worker
# ---------------------------------------------------------------------------

class _ChannelManager(IpcRuntimeProxy):
    def __init__(self, worker_id: str, channel: SubprocessPipeChannel):
        super().__init__(worker_id)
        self._start_timeout = 5.0
        self._stop_timeout = 5.0
        self._channel = channel

    async def start(self) -> None:
        self._loop = asyncio.get_event_loop()
        await self._wait_for_ready()
        self._response_task = asyncio.create_task(self._handle_responses())

    async def stop(self) -> None:
        await self._send_stop_message()
        if self._response_task is not None:
            try:
                await asyncio.wait_for(self._response_task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
        self._channel.close()

    async def _send_message(self, message: bytes) -> None:
        await self._loop.run_in_executor(None, self._channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        return await self._loop.run_in_executor(None, self._channel.recv)


class _ChannelWorker(IpcRuntimeWorker):
    def __init__(self, worker_id: str, channel: SubprocessPipeChannel):
        super().__init__(worker_id)
        self._channel = channel

    async def _start(self) -> None:
        return None

    async def _stop(self) -> None:
        return None

    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        cmd = payload["input"].get("cmd")
        if cmd == "echo":
            return {"echoed": payload["input"]["data"]}
        if cmd == "produce":
            size = payload["input"]["size"]
            chunk_size = payload["input"]["chunk_size"]
            data = bytes((i & 0xFF) for i in range(size))
            return {"stream": BytesStreamResource(data, chunk_size=chunk_size)}
        raise ValueError(f"unknown cmd: {cmd!r}")

    async def _send_message(self, message: bytes) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._channel.send, message)

    async def _recv_message(self) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._channel.recv)

    def _close_transport(self) -> None:
        self._channel.close()


def _spawn_worker_thread(worker: _ChannelWorker) -> threading.Thread:
    """Run the worker on a private asyncio loop in a background thread.

    Returns the thread; caller is responsible for joining it after issuing
    a STOP through the manager.
    """
    def _run() -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(worker.run())
        finally:
            loop.close()

    t = threading.Thread(target=_run, name=f"worker-{worker.worker_id}", daemon=True)
    t.start()
    return t


def _make_channels():
    """Return (parent_channel, worker_channel) over two OS pipe pairs."""
    a_r, a_w = os.pipe()
    b_r, b_w = os.pipe()
    parent = SubprocessPipeChannel(request_fd=b_r, response_fd=a_w)
    worker = SubprocessPipeChannel(request_fd=a_r, response_fd=b_w)
    return parent, worker


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.anyio
async def test_inline_run_over_subprocess_pipe_channel():
    """Sanity: RUN/RESULT survive the line-framed pipe transport."""
    parent_channel, worker_channel = _make_channels()
    worker = _ChannelWorker("echo", worker_channel)
    worker_thread = _spawn_worker_thread(worker)

    manager = _ChannelManager("echo", parent_channel)
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "echo", "data": "hello"},
        })
        assert result == {"echoed": "hello"}
    finally:
        await manager.stop()
        worker_thread.join(timeout=5.0)
        assert not worker_thread.is_alive(), "worker thread did not terminate"


@pytest.mark.anyio
async def test_stream_output_over_subprocess_pipe_channel():
    """The full STREAM_PULL/CHUNK/END handshake works over the real OS pipe
    transport used by the venv runtime."""
    parent_channel, worker_channel = _make_channels()
    worker = _ChannelWorker("producer", worker_channel)
    worker_thread = _spawn_worker_thread(worker)

    manager = _ChannelManager("producer", parent_channel)
    await manager.start()
    try:
        result = await manager.request({
            "action_id": "noop",
            "run_id": "r1",
            "input": {"cmd": "produce", "size": 256, "chunk_size": 32},
        })

        stream = result["stream"]
        assert isinstance(stream, StreamResource)

        received = bytearray()
        chunks = 0
        async for chunk in stream:
            received.extend(chunk)
            chunks += 1

        expected = bytes((i & 0xFF) for i in range(256))
        assert bytes(received) == expected
        assert chunks == 8  # 256 / 32
    finally:
        await manager.stop()
        worker_thread.join(timeout=5.0)
        assert not worker_thread.is_alive(), "worker thread did not terminate"
