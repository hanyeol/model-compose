from __future__ import annotations

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from .ipc_message import IpcMessage, IpcMessageType
from .ipc_stream import (
    InboundStreamProxy,
    InboundStreamState,
    OutboundStreamState,
    build_inbound_resource,
    decode_chunk_data,
    encode_chunk_data,
    push_stream_abort,
    push_stream_end,
)
import asyncio, time, ulid

class IpcRuntimeManager(ABC):
    """
    Common base for runtime managers that drive an IPC worker.

    Handles request/response correlation (pending futures), the response-handling
    loop, the start-up STATUS handshake, and standard RUN/STOP message shaping.

    Messages travel as bytes (produced by `IpcMessage.serialize`). Subclasses are
    responsible for:
    - Spawning and tearing down the child process / transport (`start` / `stop`).
    - Implementing `_send_message` / `_recv_message` over their chosen transport.

    Stream multiplexing (see component-ipc.md §3, §6, §8.2):
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
        self._inbound_streams: Dict[str, InboundStreamState] = {}
        self._outbound_streams: Dict[str, OutboundStreamState] = {}

    @abstractmethod
    async def start(self) -> None:
        pass

    @abstractmethod
    async def stop(self) -> None:
        pass

    async def execute(self, payload: Dict[str, Any]) -> Any:
        if self._loop is None:
            raise RuntimeError(f"{type(self).__name__} '{self.worker_id}' is not started")

        encoded_payload = self._codec.encode(
            payload,
            on_stream_encode=self._register_outbound_stream,
        )

        request_id = ulid.ulid()
        message = IpcMessage(
            type=IpcMessageType.RUN,
            request_id=request_id,
            payload=encoded_payload,
        )

        future: asyncio.Future = self._loop.create_future()
        self._pending_requests[request_id] = future
        await self._send_message(message.serialize())

        try:
            return await future
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
        """Drain messages from the transport and resolve pending futures."""
        try:
            while True:
                data = await self._recv_message()
                if data is None:
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
                        on_stream_decode=self._register_inbound_stream,
                    )
                    future.set_result(output)
                    continue

                if message.type == IpcMessageType.ERROR:
                    future.set_exception(Exception(payload.get("error", "Unknown error")))
                    continue
        except asyncio.CancelledError:
            pass

    # -- Stream registration callbacks (codec → manager) ----------------------

    def _register_inbound_stream(self, variable: Dict[str, Any]) -> Any:
        stream_id = variable["id"]
        kind = StreamKind(variable.get("kind", StreamKind.BYTES.value))
        state = InboundStreamState(
            stream_id=stream_id,
            kind=kind,
            queue=asyncio.Queue(),
        )
        self._inbound_streams[stream_id] = state
        proxy = InboundStreamProxy(
            state,
            on_pull=self._send_pull,
            on_close=self._send_close,
        )
        return build_inbound_resource(
            state,
            proxy,
            variable.get("content_type"),
            variable.get("filename"),
            variable.get("size"),
            variable.get("attrs") or {},
        )

    def _register_outbound_stream(self, stream_id: str, source: Any, kind: StreamKind) -> None:
        state = OutboundStreamState(
            stream_id=stream_id,
            kind=kind,
            source=source,
            iterator=source.__aiter__(),
        )
        self._outbound_streams[stream_id] = state

    # -- Stream message handling (worker → manager) ---------------------------

    async def _handle_stream_message(self, message: IpcMessage) -> None:
        payload = message.payload or {}
        stream_id = payload.get("stream_id")
        if not stream_id:
            return

        mtype = message.type

        if mtype == IpcMessageType.STREAM_PULL:
            await self._pump_outbound_once(stream_id)
            return

        if mtype == IpcMessageType.STREAM_CHUNK:
            state = self._inbound_streams.get(stream_id)
            if state is None or state.closed:
                return
            chunk = decode_chunk_data(payload.get("data"), state.kind, self._codec.decode)
            state.queue.put_nowait(chunk)
            return

        if mtype == IpcMessageType.STREAM_END:
            state = self._inbound_streams.pop(stream_id, None)
            if state is not None:
                push_stream_end(state)
            return

        if mtype == IpcMessageType.STREAM_ABORT:
            state = self._inbound_streams.pop(stream_id, None)
            if state is not None:
                push_stream_abort(state)
            outbound = self._outbound_streams.pop(stream_id, None)
            if outbound is not None:
                outbound.closed = True
            return

        if mtype == IpcMessageType.STREAM_CLOSE:
            outbound = self._outbound_streams.pop(stream_id, None)
            if outbound is not None:
                outbound.closed = True
            return

    async def _pump_outbound_once(self, stream_id: str) -> None:
        """Send exactly one chunk (or STREAM_END) in response to a STREAM_PULL.

        Credit=1 model: one PULL = one CHUNK or one END/ABORT.
        """
        state = self._outbound_streams.get(stream_id)
        if state is None or state.closed:
            return

        try:
            raw = await state.iterator.__anext__()
        except StopAsyncIteration:
            await self._send_end(stream_id)
            self._outbound_streams.pop(stream_id, None)
            return
        except Exception as e:
            await self._send_abort(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)
            return

        try:
            wire_data = encode_chunk_data(raw, state.kind, self._codec.encode)
        except Exception as e:
            await self._send_abort(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)
            return

        await self._send_chunk(stream_id, state.seq, wire_data)
        state.seq += 1

    # -- Stream send helpers --------------------------------------------------

    async def _send_pull(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_PULL,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_close(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_CLOSE,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_chunk(self, stream_id: str, seq: int, data: Any) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_CHUNK,
            payload={ "stream_id": stream_id, "seq": seq, "data": data },
        ).serialize())

    async def _send_end(self, stream_id: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_END,
            payload={ "stream_id": stream_id },
        ).serialize())

    async def _send_abort(self, stream_id: str, error: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STREAM_ABORT,
            payload={ "stream_id": stream_id, "error": error },
        ).serialize())

    async def _send_stop_message(self) -> None:
        """Best-effort STOP send; subclasses call this during their stop sequence."""
        try:
            message = IpcMessage(type=IpcMessageType.STOP, request_id=ulid.ulid())
            await self._send_message(message.serialize())
        except Exception:
            pass

    @abstractmethod
    async def _send_message(self, message: bytes) -> None:
        """Send one serialized IPC message over the transport."""
        pass

    @abstractmethod
    async def _recv_message(self) -> Optional[bytes]:
        """Receive one serialized IPC message, or return None on EOF/shutdown."""
        pass
