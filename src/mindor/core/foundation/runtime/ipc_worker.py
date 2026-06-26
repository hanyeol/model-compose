from __future__ import annotations

from typing import Any, Dict, Optional
from abc import ABC, abstractmethod
from ..variable.codec import StreamKind, VariableCodec
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
import asyncio


class IpcRuntimeWorker(ABC):
    """
    Base class for workers that communicate with a parent process via IPC.

    Subclasses define a transport (e.g., subprocess pipe, multiprocessing.Queue,
    unix socket) by implementing `_recv_message` / `_send_message` / `_close_transport`.

    Messages travel as bytes (produced by `IpcMessage.serialize`). The base
    class drives the dispatch loop and handles standard IPC message types
    (RUN, HEARTBEAT, STOP, STREAM_*) plus result/error/status notifications.

    Stream multiplexing (see component-ipc.md §3, §6, §8.2):
    - `_inbound_streams`: streams the worker consumes (RUN inputs).
    - `_outbound_streams`: streams the worker produces (RESULT outputs).
    Both are keyed by stream_id (ULID).
    """

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.running = True

        self._codec: VariableCodec = VariableCodec()
        self._inbound_streams: Dict[str, InboundStreamState] = {}
        self._outbound_streams: Dict[str, OutboundStreamState] = {}
        self._run_tasks: "set[asyncio.Task]" = set()

    async def run(self) -> None:
        try:
            await self._start()
            await self._notify_status("ready")

            while self.running:
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

                if message.type == IpcMessageType.RUN:
                    # RUN may consume an inbound stream which needs subsequent
                    # STREAM_CHUNK messages to flow. Run it as a task so the
                    # dispatch loop keeps draining the transport.
                    task = asyncio.create_task(self._run_request(message))
                    self._run_tasks.add(task)
                    task.add_done_callback(self._run_tasks.discard)
                    continue

                try:
                    await self._dispatch_message(message)
                except Exception as e:
                    await self._send_error(message.request_id, str(e))
        except Exception as e:
            await self._notify_error(str(e))
        finally:
            await self._abort_all_streams()
            for task in list(self._run_tasks):
                task.cancel()
            try:
                await self._stop()
            finally:
                self._close_transport()

    async def _run_request(self, message: IpcMessage) -> None:
        try:
            result = await self._dispatch_message(message)
            await self._send_result(message.request_id, result)
        except Exception as e:
            await self._send_error(message.request_id, str(e))

    async def _dispatch_message(self, message: IpcMessage) -> Dict[str, Any]:
        if message.type == IpcMessageType.RUN:
            decoded_input = self._codec.decode(
                message.payload or {},
                on_stream_decode=self._register_inbound_stream,
            )
            output = await self._execute_task(decoded_input)
            encoded_output = self._codec.encode(
                output,
                on_stream_encode=self._register_outbound_stream,
            )
            return { "output": encoded_output }

        if message.type == IpcMessageType.HEARTBEAT:
            return { "status": "alive" }

        if message.type == IpcMessageType.STOP:
            self.running = False
            return { "status": "stopped" }

        return { "status": "ignored" }

    # -- Stream registration callbacks (codec → worker) -----------------------

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

    # -- Stream message handling (parent → worker) ----------------------------

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

    async def _abort_all_streams(self) -> None:
        """Cleanup on worker shutdown — last-resort safety net (spec §7.2)."""
        for stream_id, state in list(self._inbound_streams.items()):
            push_stream_abort(state)
        self._inbound_streams.clear()

        for stream_id in list(self._outbound_streams.keys()):
            try:
                await self._send_abort(stream_id, "worker shutting down")
            except Exception:
                pass
        self._outbound_streams.clear()

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

    # -- Standard send helpers ------------------------------------------------

    async def _send_result(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.RESULT,
            request_id=request_id,
            payload=payload,
        ).serialize())

    async def _send_error(self, request_id: str, error: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.ERROR,
            request_id=request_id,
            payload={ "error": error },
        ).serialize())

    async def _notify_status(self, status: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STATUS,
            payload={ "status": status },
        ).serialize())

    async def _notify_error(self, error: str) -> None:
        try:
            await self._send_message(IpcMessage(
                type=IpcMessageType.ERROR,
                payload={ "error": error },
            ).serialize())
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

    @abstractmethod
    def _close_transport(self) -> None:
        """Release transport resources. Called once at run() exit."""
        pass

    # -- Worker lifecycle hooks (subclass-provided) ----------------------------

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass

    @abstractmethod
    async def _execute_task(self, payload: Dict[str, Any]) -> Any:
        pass
