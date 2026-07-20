from __future__ import annotations

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from .ipc_message import IpcMessage, IpcMessageType
from .ipc_stream import IpcInboundStream, IpcOutboundStream, IpcStreamReader
import asyncio, time, ulid

class IpcRuntimeProxy(ABC):
    """
    Common base for runtime managers that drive an IPC worker.

    Handles request/response correlation (pending futures), the response-handling
    loop, the start-up STATUS handshake, and standard RUN/STOP message shaping.

    Messages travel as bytes (produced by `IpcMessage.serialize`). Subclasses are
    responsible for:
    - Spawning and tearing down the child process / transport (`start` / `stop`).
    - Implementing `_send_message` / `_recv_message` over their chosen transport.

    Stream multiplexing:
    - `_outbound_streams`: streams the manager produces (RUN inputs).
    - `_inbound_streams`: streams the manager receives (RESULT outputs).
    Both are keyed by stream_id (ULID).
    """
    def __init__(self, worker_id: str):
        self.worker_id = worker_id

        self._pending_requests: Dict[str, asyncio.Future] = {}
        self._response_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        self._start_timeout: float = 60.0
        self._stop_timeout: float = 30.0

        self._codec: VariableCodec = VariableCodec()
        self._inbound_streams: Dict[str, IpcInboundStream] = {}
        self._outbound_streams: Dict[str, IpcOutboundStream] = {}

        # Set to a `ConnectionError` once the response loop observes EOF.
        # New `request()` calls fail fast against this instead of trying to
        # send on a dead transport (which surfaces as a noisy RuntimeError /
        # BrokenPipeError from the subclass).
        self._closed_error: Optional[ConnectionError] = None

    async def start(self) -> None:
        await self._start()

    async def stop(self) -> None:
        await self._stop()

    async def request(self, payload: Dict[str, Any]) -> Any:
        if self._loop is None:
            raise RuntimeError(f"{type(self).__name__} '{self.worker_id}' is not started")

        if self._closed_error is not None:
            raise self._closed_error

        encoded_payload = self._codec.encode(
            payload,
            on_stream_encode=self._handle_outbound_stream,
        )

        request_id = ulid.ulid()
        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id=request_id,
            payload=encoded_payload,
        )

        future: asyncio.Future = self._loop.create_future()
        self._pending_requests[request_id] = future
        try:
            await self._send_message(message.serialize())
        except Exception as e:
            # The transport tore down between our entry check and the send —
            # normalize so callers always see ConnectionError on a dead worker.
            self._pending_requests.pop(request_id, None)
            if self._closed_error is not None:
                raise self._closed_error from e
            raise ConnectionError(f"send failed on worker '{self.worker_id}': {e}") from e

        try:
            return await future
        except asyncio.CancelledError:
            # Best-effort: tell the worker to stop the in-flight request so it
            # doesn't run to completion after the caller has abandoned it.
            if self._closed_error is None:
                try:
                    await self._send_message(IpcMessage(
                        type=IpcMessageType.CANCEL,
                        request_id=request_id,
                    ).serialize())
                except Exception:
                    pass
            raise
        finally:
            self._pending_requests.pop(request_id, None)

    async def _wait_for_ready(self) -> None:
        """Block until the worker publishes STATUS=ready, or raise on timeout/error."""
        deadline = time.monotonic() + self._start_timeout

        while True:
            time_left = deadline - time.monotonic()
            if time_left <= 0:
                raise TimeoutError(f"Worker '{self.worker_id}' did not start within {self._start_timeout}s")

            try:
                data = await asyncio.wait_for(self._recv_message(), timeout=time_left)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Worker '{self.worker_id}' did not start within {self._start_timeout}s")

            if data is None:
                raise RuntimeError(f"Worker '{self.worker_id}' exited before becoming ready")

            message = IpcMessage.deserialize(data)
            payload = message.payload or {}

            if message.type == IpcMessageType.ERROR:
                raise RuntimeError(f"Worker '{self.worker_id}' failed to start: {payload.get('error', 'Unknown error')}")

            if message.type == IpcMessageType.STATUS:
                if payload.get("status") == "ready":
                    return

    async def _handle_responses(self) -> None:
        """Drain messages from the channel and resolve pending futures."""
        try:
            while True:
                data = await self._recv_message()
                if data is None:
                    self._abort_pending_on_eof()
                    break

                message = IpcMessage.deserialize(data)

                if message.type in (
                    IpcMessageType.STREAM_PULL,
                    IpcMessageType.STREAM_CHUNK,
                    IpcMessageType.STREAM_END,
                    IpcMessageType.STREAM_ABORT,
                    IpcMessageType.STREAM_CLOSE,
                ):
                    await self._handle_stream_message(message)
                    continue

                if not message.request_id:
                    continue

                future = self._pending_requests.get(message.request_id)
                if future is None or future.done():
                    continue

                payload = message.payload or {}

                if message.type == IpcMessageType.RESULT:
                    output = self._codec.decode(
                        payload.get("output"),
                        on_stream_decode=self._handle_inbound_stream,
                    )
                    future.set_result(output)
                    continue

                if message.type == IpcMessageType.ERROR:
                    future.set_exception(Exception(payload.get("error", "Unknown error")))
                    continue
        except asyncio.CancelledError:
            pass

    def _abort_pending_on_eof(self, error: str = "worker transport closed") -> None:
        """Fail pending requests / inbound streams on transport EOF and latch
        `_closed_error` so later `request()` calls fail fast. Idempotent."""
        exc = self._closed_error or ConnectionError(error)
        self._closed_error = exc

        for stream in list(self._inbound_streams.values()):
            stream.push_abort()
        self._inbound_streams.clear()
        self._outbound_streams.clear()

        for future in list(self._pending_requests.values()):
            if not future.done():
                future.set_exception(exc)
        self._pending_requests.clear()

    def _handle_inbound_stream(self, variable: Dict[str, Any]) -> Any:
        stream_id = variable["id"]
        kind = StreamKind(variable.get("kind", StreamKind.BYTES.value))
        stream = IpcInboundStream(stream_id=stream_id, kind=kind, codec=self._codec)
        self._inbound_streams[stream_id] = stream

        return stream.build_resource(
            IpcStreamReader(
                stream,
                on_pull=self._send_stream_pull_message,
                on_close=self._send_stream_close_message,
            ),
            variable.get("content_type"),
            variable.get("filename"),
            variable.get("size"),
            variable.get("attrs") or {},
        )

    def _handle_outbound_stream(self, stream_id: str, source: Any, kind: StreamKind) -> None:
        stream = IpcOutboundStream(stream_id=stream_id, kind=kind, source=source, codec=self._codec)
        self._outbound_streams[stream_id] = stream

    async def _handle_stream_message(self, message: IpcMessage) -> None:
        payload = message.payload or {}
        stream_id = payload.get("stream_id")
        if not stream_id:
            return

        mtype = message.type

        if mtype == IpcMessageType.STREAM_PULL:
            await self._pump_outbound_chunk(stream_id)
            return

        if mtype == IpcMessageType.STREAM_CHUNK:
            stream = self._inbound_streams.get(stream_id)
            if stream is None or stream.closed:
                return
            # BYTES chunks travel in the binary trailer; other kinds ride in payload.data.
            data = message.binary if stream.kind == StreamKind.BYTES else payload.get("data")
            chunk = stream.decode_chunk(data)
            stream.queue.put_nowait(chunk)
            return

        if mtype == IpcMessageType.STREAM_END:
            stream = self._inbound_streams.pop(stream_id, None)
            if stream is not None:
                stream.push_end()
            return

        if mtype == IpcMessageType.STREAM_ABORT:
            stream = self._inbound_streams.pop(stream_id, None)
            if stream is not None:
                stream.push_abort()
            outbound = self._outbound_streams.pop(stream_id, None)
            if outbound is not None:
                outbound.closed = True
            return

        if mtype == IpcMessageType.STREAM_CLOSE:
            outbound = self._outbound_streams.pop(stream_id, None)
            if outbound is not None:
                outbound.closed = True
            return

    async def _pump_outbound_chunk(self, stream_id: str) -> None:
        """Send exactly one chunk (or STREAM_END) in response to a STREAM_PULL.

        Credit=1 model: one PULL = one CHUNK or one END/ABORT.
        """
        stream = self._outbound_streams.get(stream_id)
        if stream is None or stream.closed:
            return

        try:
            chunk = await stream.next_chunk()
        except StopAsyncIteration:
            await self._send_stream_end_message(stream_id)
            self._outbound_streams.pop(stream_id, None)
            return
        except Exception as e:
            await self._send_stream_abort_message(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)
            return

        try:
            chunk = stream.encode_chunk(chunk)
        except Exception as e:
            await self._send_stream_abort_message(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)
            return

        await self._send_stream_chunk_message(stream_id, stream.seq, chunk)
        stream.seq += 1

    async def _send_start_message(self, payload: Optional[Dict[str, Any]] = None) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.START,
            payload=payload,
        ).serialize())

    async def _send_stop_message(self) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STOP,
            request_id=ulid.ulid()
        ).serialize())

    async def _send_stream_pull_message(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_PULL,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_stream_close_message(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_CLOSE,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_stream_chunk_message(self, stream_id: str, seq: int, data: Any) -> None:
        # BYTES chunks travel out-of-band in the binary trailer to avoid base64 overhead.
        if isinstance(data, (bytes, bytearray)):
            message = IpcMessage(
                type=IpcMessageType.STREAM_CHUNK,
                payload={ "stream_id": stream_id, "seq": seq },
                binary=bytes(data),
            )
        else:
            message = IpcMessage(
                type=IpcMessageType.STREAM_CHUNK,
                payload={ "stream_id": stream_id, "seq": seq, "data": data },
            )
        await self._send_message(message.serialize())

    async def _send_stream_end_message(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_END,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_stream_abort_message(self, stream_id: str, error: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_ABORT,
            payload={ "stream_id": stream_id, "error": error },
        ).serialize())

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass

    @abstractmethod
    async def _send_message(self, message: bytes) -> None:
        """Send one serialized IPC message over the transport."""
        pass

    @abstractmethod
    async def _recv_message(self) -> Optional[bytes]:
        """Receive one serialized IPC message, or return None on EOF/shutdown."""
        pass
