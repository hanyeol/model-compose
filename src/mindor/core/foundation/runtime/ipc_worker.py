from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional, Union
from abc import ABC, abstractmethod
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from mindor.core.utils.json import to_json_safe
from .ipc_message import IpcMessage, IpcMessageType
from .ipc_stream import IpcInboundStream, IpcOutboundStream, IpcStreamReader
import asyncio, traceback, ulid

class IpcRuntimeWorker(ABC):
    """
    Base class for workers that communicate with a parent process via IPC.

    Subclasses define a transport (e.g., subprocess pipe, multiprocessing.Queue,
    unix socket) by implementing `_recv_message` / `_send_message` / `_close_transport`.

    Messages travel as bytes (produced by `IpcMessage.serialize`). The base
    class drives the dispatch loop and handles standard IPC message types
    (RUN, HEARTBEAT, STOP, STREAM_*) plus result/error/status notifications.

    Stream multiplexing:
    - `_inbound_streams`: streams the worker consumes (RUN inputs).
    - `_outbound_streams`: streams the worker produces (RESULT outputs).
    Both are keyed by stream_id (ULID).
    """
    def __init__(self, worker_id: str):
        self.worker_id = worker_id

        self._codec: VariableCodec = VariableCodec()
        self._inbound_streams: Dict[str, IpcInboundStream] = {}
        self._outbound_streams: Dict[str, IpcOutboundStream] = {}
        self._run_tasks: Dict[str, asyncio.Task] = {}

        # Outbound CALL state: `call(...)` registers a future keyed by call_id
        # and dispatches CALL_RESULT / CALL_ERROR messages back to it.
        self._pending_calls: Dict[str, asyncio.Future] = {}

    async def run(self) -> None:
        try:
            await self._start()
            await self._notify_status("ready")

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

                if message.type in (IpcMessageType.CALL_RESULT, IpcMessageType.CALL_ERROR):
                    self._resolve_outbound_call(message)

                    continue

                if message.type == IpcMessageType.RUN:
                    # RUN may consume an inbound stream which needs subsequent
                    # STREAM_CHUNK messages to flow. Run it as a task so the
                    # dispatch loop keeps draining the transport.
                    request_id = message.request_id
                    task = asyncio.create_task(self._run_request(message))

                    if request_id:
                        self._run_tasks[request_id] = task
                        task.add_done_callback(lambda _t, rid=request_id: self._run_tasks.pop(rid, None))

                    continue

                if message.type == IpcMessageType.CANCEL:
                    target_request_id = message.request_id

                    if target_request_id:
                        target = self._run_tasks.get(target_request_id)

                        if target is not None and not target.done():
                            target.cancel()

                    continue

                if message.type == IpcMessageType.STOP:
                    # Reply first so the parent's `request()` future resolves,
                    # then exit the dispatch loop; shutdown runs in `finally`.
                    await self._send_result(message.request_id, { "status": "stopped" })
                    break

                try:
                    await self._dispatch_message(message)
                except Exception as e:
                    await self._send_error(message.request_id, e)
        except Exception as e:
            await self._notify_error(e)
        finally:
            await self._abort_all_streams()

            for task in list(self._run_tasks.values()):
                task.cancel()

            eof_error = ConnectionError("parent transport closed")
            for future in list(self._pending_calls.values()):
                if not future.done():
                    future.set_exception(eof_error)

            self._pending_calls.clear()

            try:
                await self._stop()
            finally:
                self._close_transport()

    async def call(self, payload: Dict[str, Any]) -> Any:
        """Issue a reverse-direction CALL to the parent and await its result.

        The payload is codec-encoded (streams and tensors inside are supported);
        the returned output is codec-decoded. Cancellation sends CALL_CANCEL to
        the parent so the parent-side handler can abort its own work.
        """
        loop = asyncio.get_event_loop()
        call_id = ulid.ulid()
        future: asyncio.Future = loop.create_future()
        self._pending_calls[call_id] = future

        encoded_payload = self._codec.encode(
            payload,
            on_stream_encode=self._build_outbound_stream_handler("call", call_id),
        )

        try:
            await self._send_message(IpcMessage(
                type=IpcMessageType.CALL,
                request_id=call_id,
                payload=encoded_payload,
            ).serialize())
        except Exception:
            self._pending_calls.pop(call_id, None)
            await self._abort_streams_for_owner("call", call_id)
            raise

        try:
            return await future
        except asyncio.CancelledError:
            try:
                await self._send_message(IpcMessage(
                    type=IpcMessageType.CALL_CANCEL,
                    request_id=call_id,
                ).serialize())
            except Exception:
                pass

            await self._abort_streams_for_owner("call", call_id)
            raise
        finally:
            self._pending_calls.pop(call_id, None)

    def _resolve_outbound_call(self, message: IpcMessage) -> None:
        call_id = message.request_id

        if not call_id:
            return

        future = self._pending_calls.get(call_id)

        if future is None or future.done():
            return

        payload = message.payload or {}

        if message.type == IpcMessageType.CALL_RESULT:
            try:
                output = self._codec.decode(payload.get("output"), on_stream_decode=self._handle_inbound_stream)
            except Exception as e:
                future.set_exception(e)
                return

            future.set_result(output)
            return

        # CALL_ERROR
        error_message = payload.get("error") or "Unknown error"
        traceback_message = payload.get("traceback")

        if traceback_message:
            error_message = f"{error_message}\n\nParent traceback:\n{traceback_message}"

        future.set_exception(Exception(error_message))

    async def _run_request(self, message: IpcMessage) -> None:
        try:
            result = await self._dispatch_message(message)
            await self._send_result(message.request_id, result)
        except asyncio.CancelledError:
            if message.request_id:
                await self._abort_streams_for_owner("run", message.request_id)

            await self._send_error(message.request_id, "Request was cancelled")
            raise
        except Exception as e:
            if message.request_id:
                await self._abort_streams_for_owner("run", message.request_id)

            await self._send_error(message.request_id, e)

    async def _dispatch_message(self, message: IpcMessage) -> Dict[str, Any]:
        if message.type == IpcMessageType.RUN:
            input = self._codec.decode(
                message.payload or {},
                on_stream_decode=self._handle_inbound_stream,
            )
            request_id = message.request_id

            async def _send_event(payload: Dict[str, Any]) -> None:
                if request_id is not None:
                    await self._send_event(request_id, to_json_safe(payload))

            output = await self._execute_task(input, on_event=_send_event)
            output = self._codec.encode(
                output,
                on_stream_encode=self._build_outbound_stream_handler("run", request_id),
            )

            return { "output": output }

        if message.type == IpcMessageType.HEARTBEAT:
            return { "status": "alive" }

        return { "status": "ignored" }

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

    def _build_outbound_stream_handler(
        self,
        owner_kind: str,
        owner_id: str,
    ) -> Callable[[str, Any, StreamKind], None]:
        """Build a stream-encode callback that tags each registered stream with
        its owning request / call. Matches `IpcRuntimeProxy._build_outbound_stream_handler`."""
        def _handle_outbound_stream(stream_id: str, source: Any, kind: StreamKind) -> None:
            self._outbound_streams[stream_id] = IpcOutboundStream(
                stream_id=stream_id,
                kind=kind,
                source=source,
                codec=self._codec,
                owner_kind=owner_kind,
                owner_id=owner_id,
            )

        return _handle_outbound_stream

    async def _handle_stream_message(self, message: IpcMessage) -> None:
        payload = message.payload or {}
        stream_id = payload.get("stream_id")

        if not stream_id:
            return

        if message.type == IpcMessageType.STREAM_PULL:
            # Spawn pump as a child task so the dispatch loop can still process
            # STREAM_CLOSE / STREAM_ABORT for this same stream mid-pull — the
            # handler cancels the pump task to interrupt a slow iterator.
            asyncio.create_task(self._pump_outbound_chunk(stream_id))

            return

        if message.type == IpcMessageType.STREAM_CHUNK:
            stream = self._inbound_streams.get(stream_id)
            if stream is None or stream.closed:
                return
            # BYTES chunks travel in the binary trailer; other kinds ride in payload.data.
            data = message.binary if stream.kind == StreamKind.BYTES else payload.get("data")
            chunk = stream.decode_chunk(data)
            stream.queue.put_nowait(chunk)

            return

        if message.type == IpcMessageType.STREAM_END:
            stream = self._inbound_streams.pop(stream_id, None)

            if stream is not None:
                stream.push_end()

            return

        if message.type == IpcMessageType.STREAM_ABORT:
            stream = self._inbound_streams.pop(stream_id, None)

            if stream is not None:
                stream.push_abort()

            outbound = self._outbound_streams.pop(stream_id, None)

            if outbound is not None:
                await outbound.aclose()

            return

        if message.type == IpcMessageType.STREAM_CLOSE:
            outbound = self._outbound_streams.pop(stream_id, None)

            if outbound is not None:
                await outbound.aclose()

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
        except asyncio.CancelledError:
            # We cancelled this pull ourselves (via `aclose()`) to tear down a
            # slow iterator — not an upstream task cancel. Swallow it; the
            # STREAM_CLOSE/ABORT handler already sent the wire message and
            # removed us from `_outbound_streams`.
            return
        except Exception as e:
            await self._send_stream_abort_message(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)

            return

        # If close/abort landed between pull and send, don't ship an orphaned
        # chunk. The handler already evicted us; just drop it.
        if stream.closed:
            return

        try:
            chunk = stream.encode_chunk(chunk)
        except Exception as e:
            await self._send_stream_abort_message(stream_id, str(e))
            self._outbound_streams.pop(stream_id, None)

            return

        await self._send_stream_chunk_message(stream_id, stream.seq, chunk)
        stream.seq += 1

    async def _abort_streams_for_owner(self, owner_kind: str, owner_id: str) -> None:
        """Abort every outbound stream tagged with the given owner — used when
        the owning RUN/CALL is cancelled on this side. Also tears down the
        source iterator so its `finally` blocks run."""
        matches = [
            (stream_id, stream) for stream_id, stream in self._outbound_streams.items()
            if stream.owner_kind == owner_kind and stream.owner_id == owner_id and not stream.closed
        ]

        for stream_id, stream in matches:
            self._outbound_streams.pop(stream_id, None)

            try:
                await self._send_stream_abort_message(stream_id, "owner cancelled")
            except Exception:
                pass

            try:
                await stream.aclose()
            except Exception:
                pass

    async def _abort_all_streams(self) -> None:
        """Cleanup on worker shutdown — last-resort safety net."""
        for stream_id, stream in list(self._inbound_streams.items()):
            stream.push_abort()

        self._inbound_streams.clear()

        for stream_id in list(self._outbound_streams.keys()):
            try:
                await self._send_stream_abort_message(stream_id, "worker shutting down")
            except Exception:
                pass

        self._outbound_streams.clear()

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

    async def _send_result(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.RESULT,
            request_id=request_id,
            payload=payload,
        ).serialize())

    async def _send_error(self, request_id: str, error: Union[BaseException, str]) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.ERROR,
            request_id=request_id,
            payload=self._build_error_payload(error),
        ).serialize())

    async def _send_event(self, request_id: str, payload: Dict[str, Any]) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.EVENT,
            request_id=request_id,
            payload=payload,
        ).serialize())

    async def _notify_status(self, status: str) -> None:
        await self._send_message(IpcMessage(
            type=IpcMessageType.STATUS,
            payload={ "status": status },
        ).serialize())

    async def _notify_error(self, error: Union[BaseException, str]) -> None:
        try:
            await self._send_message(IpcMessage(
                type=IpcMessageType.ERROR,
                payload=self._build_error_payload(error),
            ).serialize())
        except Exception:
            pass

    def _build_error_payload(self, error: Union[BaseException, str]) -> Dict[str, Any]:
        if isinstance(error, BaseException):
            return {
                "error":     str(error) or type(error).__name__,
                "traceback": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
            }
        return { "error": error }

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

    @abstractmethod
    def _close_transport(self) -> None:
        """Release transport resources. Called once at run() exit."""
        pass

    @abstractmethod
    async def _execute_task(
        self,
        payload: Dict[str, Any],
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Any:
        pass
