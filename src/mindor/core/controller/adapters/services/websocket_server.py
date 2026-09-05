from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Any, Callable, get_type_hints
from collections.abc import AsyncIterator
from pydantic import BaseModel, Field, ValidationError
from mindor.dsl.schema.controller.adapter.impl.http_server import WebSocketConfig
from mindor.core.controller.base import TaskState, TaskEvent, JobEvent
from mindor.core.errors import TaskError
from mindor.core.logger import logging
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator
from mindor.core.foundation.variable.codec import StreamKind, VariableCodec
from .websocket_stream import (
    WebSocketInboundStream,
    WebSocketOutboundStream,
    WebSocketStreamReader,
    WebSocketStreamRegistry,
)
from fastapi import APIRouter, WebSocket
from PIL import Image as PILImage
from datetime import datetime, timezone
import json, ulid, asyncio, inspect, functools

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class WebSocketMessage(BaseModel):
    type: str
    id: Optional[str] = None
    data: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WorkflowRunPayload(BaseModel):
    workflow_id: Optional[str] = None
    input: Optional[Any] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None
    subscribe_task: bool = True

class TaskSubscribePayload(BaseModel):
    task_id: str

class TaskUnsubscribePayload(BaseModel):
    task_id: str

class TaskResumePayload(BaseModel):
    task_id: str
    job_id: str
    run_id: Optional[str] = None
    answer: Optional[Any] = None

class TaskGetPayload(BaseModel):
    task_id: str

class PingPayload(BaseModel):
    pass

class StreamPullPayload(BaseModel):
    id: str

class StreamEndPayload(BaseModel):
    id: str

class StreamAbortPayload(BaseModel):
    id: str
    reason: Optional[str] = None

class StreamClosePayload(BaseModel):
    id: str

class WorkflowStartedResult(BaseModel):
    task_id: str
    workflow_id: str
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]

class TaskSubscribedResult(BaseModel):
    task_id: str
    state: Dict[str, Any]

class TaskUnsubscribedResult(BaseModel):
    task_id: str

class TaskResumedResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]

class WebSocketManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._task_subscribers: Dict[str, Set[str]] = {}
        self._client_subscriptions: Dict[str, Set[str]] = {}

    async def accept(self, client_id: str, websocket: WebSocket) -> bool:
        if client_id in self._connections:
            await websocket.close(code=4409, reason="Session already connected")
            return False

        await websocket.accept()

        self._connections[client_id] = websocket
        self._client_subscriptions[client_id] = set()

        return True

    async def send_message(self, client_id: str, message: WebSocketMessage) -> None:
        websocket = self._connections.get(client_id)

        if not websocket:
            logging.warning("Dropped WebSocket message for unknown client %s (type=%s)", client_id, message.type)
            return

        await websocket.send_text(self._serialize_message(message))

    async def send_bytes(self, client_id: str, payload: bytes) -> None:
        websocket = self._connections.get(client_id)

        if not websocket:
            logging.warning("Dropped WebSocket binary frame for unknown client %s (%d bytes)", client_id, len(payload))
            return

        await websocket.send_bytes(payload)

    async def broadcast_task_message(self, task_id: str, message: WebSocketMessage) -> None:
        subscribers = self._task_subscribers.get(task_id)

        if not subscribers:
            return

        message_text = self._serialize_message(message)
        connections = [ self._connections[client_id] for client_id in subscribers if client_id in self._connections ]
        tasks = [ websocket.send_text(message_text) for websocket in connections ]

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def send_error(self, client_id: str, code: str, message: str, message_id: Optional[str] = None) -> None:
        await self.send_message(client_id, WebSocketMessage(
            type="error",
            id=message_id,
            data={"code": code, "message": message},
        ))

    def subscribe_task(self, client_id: str, task_id: str) -> None:
        if task_id not in self._task_subscribers:
            self._task_subscribers[task_id] = set()

        self._task_subscribers[task_id].add(client_id)

        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].add(task_id)

    def unsubscribe_task(self, client_id: str, task_id: str) -> None:
        if task_id in self._task_subscribers:
            self._task_subscribers[task_id].discard(client_id)

            if not self._task_subscribers[task_id]:
                del self._task_subscribers[task_id]

        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].discard(task_id)

    def task_subscribers(self, task_id: str) -> Set[str]:
        return set(self._task_subscribers.get(task_id, ()))

    def has_task_subscribers(self, task_id: str) -> bool:
        return bool(self._task_subscribers.get(task_id))

    def has_connection(self, client_id: str) -> bool:
        return client_id in self._connections

    async def close(self, client_id: str) -> None:
        subscriptions = self._client_subscriptions.pop(client_id, None)

        for task_id in subscriptions or []:
            subscribers = self._task_subscribers.get(task_id)

            if subscribers is not None:
                subscribers.discard(client_id)

                if not subscribers:
                    self._task_subscribers.pop(task_id, None)

        self._connections.pop(client_id, None)

    async def dispose(self) -> None:
        for websocket in self._connections.values():
            await websocket.close()

        self._connections.clear()
        self._task_subscribers.clear()
        self._client_subscriptions.clear()

    def _serialize_message(self, message: WebSocketMessage) -> str:
        return json.dumps(
            message.model_dump(exclude_none=True, mode="json"),
            ensure_ascii=False,
            default=str
        )

class WebSocketRouter:
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}

    def handler(self, message_type: str):
        def decorator(func: Callable) -> Callable:
            payload_type = self._infer_payload_type(func)

            if payload_type is not None:
                @functools.wraps(func)
                async def _wrapper(client_id: str, message_id: Optional[str], data: dict):
                    return await func(client_id, message_id, payload_type(**data))
                self._handlers[message_type] = _wrapper
            else:
                self._handlers[message_type] = func

            return func

        return decorator

    def resolve(self, message_type: str) -> Optional[Callable]:
        return self._handlers.get(message_type)

    @staticmethod
    def _infer_payload_type(func: Callable) -> Optional[type]:
        try:
            hints = get_type_hints(func)
        except Exception:
            return None

        params = list(inspect.signature(func).parameters.values())

        if not params:
            return None

        payload_type = hints.get(params[-1].name)

        if isinstance(payload_type, type) and issubclass(payload_type, BaseModel):
            return payload_type

        return None

class WebSocketServer:
    def __init__(
        self,
        config: WebSocketConfig,
        controller: ControllerService,
        resolve_workflow_id: Callable[[str], Optional[str]],
    ):
        self.config = config
        self.controller = controller
        self.manager: WebSocketManager = WebSocketManager()
        self.router: WebSocketRouter = WebSocketRouter()
        self.streams: WebSocketStreamRegistry = WebSocketStreamRegistry()
        self.codec: VariableCodec = VariableCodec()

        self._resolve_workflow_id = resolve_workflow_id

    def configure_routes(self, router: APIRouter) -> None:
        @router.websocket(self.config.path)
        async def serve_websocket(
            websocket: WebSocket,
            session: Optional[str] = None,
            task: Optional[str] = None,
        ):
            if self.config.max_connection_count and len(self.manager._connections) >= self.config.max_connection_count:
                await websocket.close(code=4429, reason="Too many connections")
                return

            client_id = session if session else ulid.ulid()
            accepted = await self.manager.accept(client_id, websocket)

            if not accepted:
                return

            if task:
                state = self.controller.get_task_state(task)

                if state:
                    self.manager.subscribe_task(client_id, task)
                    await self.manager.send_message(client_id, WebSocketMessage(
                        type="task_subscribed",
                        data=TaskSubscribedResult(
                            task_id=task,
                            state=self._task_state_to_dict(state),
                        ).model_dump(exclude_none=True),
                    ))
                else:
                    await self.manager.send_message(client_id, WebSocketMessage(
                        type="error",
                        data={
                            "code": "TASK_NOT_FOUND",
                            "message": f"Task '{task}' not found",
                        },
                    ))

            try:
                while True:
                    frame = await websocket.receive()

                    if frame.get("type") == "websocket.disconnect":
                        break

                    if (payload_bytes := frame.get("bytes")) is not None:
                        await self._handle_binary_frame(client_id, payload_bytes)
                        continue

                    message_text = frame.get("text")

                    if message_text is None:
                        continue

                    try:
                        message = WebSocketMessage(**json.loads(message_text))
                    except json.JSONDecodeError:
                        await self.manager.send_error(client_id, "INVALID_REQUEST", "Invalid JSON")
                        continue
                    except Exception as e:
                        await self.manager.send_error(client_id, "INVALID_REQUEST", f"Invalid message: {e}")
                        continue

                    handler = self.router.resolve(message.type)

                    if handler:
                        try:
                            await handler(client_id, message.id, message.data)
                        except ValidationError as e:
                            await self.manager.send_error(client_id, "INVALID_REQUEST", f"Invalid data: {e}", message.id)
                        except Exception as e:
                            await self.manager.send_error(client_id, "INTERNAL_ERROR", str(e), message.id)
                    else:
                        await self.manager.send_error(client_id, "INVALID_REQUEST", f"Unknown message type: {message.type}", message.id)
            finally:
                await self.streams.close(client_id)
                await self.manager.close(client_id)

        @self.router.handler("run_workflow")
        async def run_workflow(client_id: str, message_id: Optional[str], payload: WorkflowRunPayload) -> None:
            workflow_id = self._resolve_workflow_id(payload.workflow_id or "__default__")

            if not workflow_id or not self.controller.is_workflow_available(workflow_id):
                await self.manager.send_error(client_id, "WORKFLOW_NOT_FOUND", f"Workflow '{payload.workflow_id or '__default__'}' not found", message_id)
                return

            try:
                input = self._decode_stream_input(client_id, payload.input) if payload.input is not None else None
            except Exception as e:
                await self.manager.send_error(client_id, "INVALID_REQUEST", f"Invalid stream input: {e}", message_id)
                return

            state = await self.controller.run_workflow(
                workflow_id,
                input,
                wait_for_completion=False,
                session_id=payload.session_id,
                metadata=payload.metadata,
            )

            if payload.subscribe_task:
                self.manager.subscribe_task(client_id, state.task_id)

            await self.manager.send_message(client_id, WebSocketMessage(
                type="workflow_started",
                id=message_id,
                data=WorkflowStartedResult(
                    task_id=state.task_id,
                    workflow_id=workflow_id,
                    status=state.status,
                ).model_dump(exclude_none=True),
            ))

            if payload.subscribe_task:
                state = self.controller.get_task_state(state.task_id)

                if state and state.status != state.status:
                    await self.manager.send_message(client_id, WebSocketMessage(
                        type="task_state",
                        data=self._task_state_to_dict(state)
                    ))

        @self.router.handler("subscribe_task")
        async def subscribe_task(client_id: str, message_id: Optional[str], payload: TaskSubscribePayload) -> None:
            state = self.controller.get_task_state(payload.task_id)

            if not state:
                await self.manager.send_error(client_id, "TASK_NOT_FOUND", f"Task '{payload.task_id}' not found", message_id)
                return

            self.manager.subscribe_task(client_id, payload.task_id)

            await self.manager.send_message(client_id, WebSocketMessage(
                type="task_subscribed",
                id=message_id,
                data=TaskSubscribedResult(
                    task_id=payload.task_id,
                    state=self._task_state_to_dict(state),
                ).model_dump(exclude_none=True),
            ))

        @self.router.handler("unsubscribe_task")
        async def unsubscribe_task(client_id: str, message_id: Optional[str], payload: TaskUnsubscribePayload) -> None:
            self.manager.unsubscribe_task(client_id, payload.task_id)

            await self.manager.send_message(client_id, WebSocketMessage(
                type="task_unsubscribed",
                id=message_id,
                data=TaskUnsubscribedResult(
                    task_id=payload.task_id
                ).model_dump(exclude_none=True),
            ))

        @self.router.handler("resume_task")
        async def resume_task(client_id: str, message_id: Optional[str], payload: TaskResumePayload) -> None:
            try:
                state = await self.controller.resume_workflow(payload.task_id, payload.job_id, payload.run_id, payload.answer)

                await self.manager.send_message(client_id, WebSocketMessage(
                    type="task_resumed",
                    id=message_id,
                    data=TaskResumedResult(
                        task_id=payload.task_id,
                        status=state.status,
                    ).model_dump(exclude_none=True),
                ))
            except TaskError as e:
                await self.manager.send_error(client_id, e.code, str(e), message_id)

        @self.router.handler("get_task")
        async def get_task(client_id: str, message_id: Optional[str], payload: TaskGetPayload) -> None:
            state = self.controller.get_task_state(payload.task_id)

            if not state:
                await self.manager.send_error(client_id, "TASK_NOT_FOUND", f"Task '{payload.task_id}' not found", message_id)
                return

            await self.manager.send_message(client_id, WebSocketMessage(
                type="task_state",
                id=message_id,
                data=self._task_state_to_dict(state)
            ))

        @self.router.handler("stream_end")
        async def stream_end(client_id: str, message_id: Optional[str], payload: StreamEndPayload) -> None:
            stream = self.streams.get_inbound(client_id, payload.id)

            if stream is None:
                return

            stream.push_end()

        @self.router.handler("stream_abort")
        async def stream_abort(client_id: str, message_id: Optional[str], payload: StreamAbortPayload) -> None:
            stream = self.streams.get_inbound(client_id, payload.id)

            if stream is None:
                return

            stream.push_abort()

        @self.router.handler("stream_pull")
        async def stream_pull(client_id: str, message_id: Optional[str], payload: StreamPullPayload) -> None:
            stream = self.streams.get_outbound(client_id, payload.id)

            if stream is None:
                await self.manager.send_error(client_id, "STREAM_NOT_FOUND", f"Outbound stream '{payload.id}' not found", message_id)
                return

            if not stream.closed:
                await self._stream_to_outbound(client_id, stream)

        @self.router.handler("stream_close")
        async def stream_close(client_id: str, message_id: Optional[str], payload: StreamClosePayload) -> None:
            stream = self.streams.remove_outbound(client_id, payload.id)

            if stream is None:
                return

            stream.closed = True
            await stream.aclose()

        @self.router.handler("ping")
        async def ping(client_id: str, message_id: Optional[str], payload: PingPayload) -> None:
            await self.manager.send_message(client_id, WebSocketMessage(
                type="pong",
                id=message_id,
            ))

    async def notify_task_subscribed(self, client_id: str, state: TaskState) -> None:
        await self.manager.send_message(client_id, WebSocketMessage(
            type="task_state",
            data=self._task_state_to_dict(state),
        ))

    async def broadcast_task_state(self, task_id: str, state: TaskState) -> None:
        if not self.manager.has_task_subscribers(task_id):
            return

        base = self._task_state_to_dict(state)
        await self._broadcast_with_output(task_id, "task_state", base, state.output)

    async def broadcast_task_event(self, event: TaskEvent) -> None:
        if not self.manager.has_task_subscribers(event.task_id):
            return

        base = self._task_event_to_dict(event)
        await self._broadcast_with_output(event.task_id, "task_event", base, event.output)

    async def broadcast_job_event(self, event: JobEvent) -> None:
        if not self.manager.has_task_subscribers(event.task_id):
            return

        base = self._job_event_to_dict(event)
        await self._broadcast_with_output(event.task_id, "job_event", base, event.output)

    async def dispose(self) -> None:
        await self.manager.dispose()

    async def _broadcast_with_output(
        self,
        task_id: str,
        message_type: str,
        base_data: Dict[str, Any],
        output: Any,
    ) -> None:
        if not self._contains_stream(output):
            await self.manager.broadcast_task_message(
                task_id,
                WebSocketMessage(type=message_type, data=base_data),
            )
            return

        for client_id in self.manager.task_subscribers(task_id):
            data = dict(base_data)
            data["output"] = self._encode_stream_output(client_id, output)

            await self.manager.send_message(
                client_id,
                WebSocketMessage(type=message_type, data=data),
            )

    async def _handle_binary_frame(self, client_id: str, payload: bytes) -> None:
        try:
            stream_id, _, chunk = WebSocketInboundStream.decode_frame(payload)
        except ValueError as e:
            await self.manager.send_error(client_id, "INVALID_REQUEST", f"Invalid chunk frame: {e}")
            return

        stream = self.streams.get_inbound(client_id, stream_id)
        if stream is None:
            await self.manager.send_error(client_id, "STREAM_NOT_FOUND", f"Inbound stream '{stream_id}' not found")
            return

        try:
            decoded = stream.decode_chunk(chunk)
        except Exception as e:
            await self.manager.send_error(client_id, "INVALID_REQUEST", f"Chunk decode failed: {e}")
            return

        stream.push_chunk(decoded)

    def _decode_stream_input(self, client_id: str, value: Any) -> Any:
        def on_stream_decode(variable: Dict[str, Any]) -> Any:
            stream_id = variable.get("id")

            if not isinstance(stream_id, str):
                raise ValueError("stream variable missing 'id'")

            kind_value = variable.get("kind")

            try:
                kind = StreamKind(kind_value)
            except ValueError:
                raise ValueError(f"unknown stream kind: {kind_value!r}")

            inbound = WebSocketInboundStream(stream_id, kind, self.codec)
            self.streams.register_inbound(client_id, inbound)

            reader = WebSocketStreamReader(
                inbound,
                on_pull=lambda sid: self.manager.send_message(
                    client_id,
                    WebSocketMessage(type="stream_pull", data={"id": sid}),
                ),
                on_close=lambda sid: self._close_inbound(client_id, sid),
            )

            return inbound.build_resource(
                reader,
                content_type=variable.get("content_type"),
                filename=variable.get("filename"),
                size=variable.get("size"),
                attrs=variable.get("attrs") or {},
            )

        return self.codec.decode(value, on_stream_decode)

    async def _close_inbound(self, client_id: str, stream_id: str) -> None:
        stream = self.streams.remove_inbound(client_id, stream_id)

        if stream is None:
            return

        stream.closed = True

        await self.manager.send_message(
            client_id,
            WebSocketMessage(type="stream_close", data={"id": stream_id}),
        )

    async def _stream_to_outbound(self, client_id: str, stream: WebSocketOutboundStream) -> None:
        try:
            chunk = await stream.next_chunk()
        except StopAsyncIteration:
            stream.closed = True
            self.streams.remove_outbound(client_id, stream.stream_id)

            await self.manager.send_message(
                client_id,
                WebSocketMessage(type="stream_end", data={"id": stream.stream_id}),
            )
            return
        except Exception as e:
            stream.closed = True
            self.streams.remove_outbound(client_id, stream.stream_id)

            await self.manager.send_message(
                client_id,
                WebSocketMessage(type="stream_abort", data={"id": stream.stream_id, "reason": str(e)}),
            )
            return

        try:
            chunk = stream.encode_chunk(chunk)
        except Exception as e:
            stream.closed = True
            self.streams.remove_outbound(client_id, stream.stream_id)

            await self.manager.send_message(
                client_id,
                WebSocketMessage(type="stream_abort", data={"id": stream.stream_id, "reason": str(e)}),
            )
            return

        if stream.kind == StreamKind.BYTES:
            await self.manager.send_bytes(client_id, stream.encode_frame(chunk))
        else:
            seq = stream.seq
            stream.seq += 1

            await self.manager.send_message(
                client_id,
                WebSocketMessage(
                    type="stream_chunk",
                    data={"id": stream.stream_id, "seq": seq, "value": chunk},
                ),
            )

    def _encode_stream_output(self, client_id: str, value: Any) -> Any:
        def on_stream_encode(stream_id: str, source: Any, kind: StreamKind) -> None:
            outbound = WebSocketOutboundStream(stream_id, kind, source, self.codec)
            self.streams.register_outbound(client_id, outbound)

        return self.codec.encode(value, on_stream_encode)

    @staticmethod
    def _contains_stream(value: Any) -> bool:
        if isinstance(value, (StreamResource, StreamIterator, AsyncIterator, PILImage.Image)):
            return True

        if isinstance(value, dict):
            return any(WebSocketServer._contains_stream(v) for v in value.values())

        if isinstance(value, (list, tuple)):
            return any(WebSocketServer._contains_stream(v) for v in value)
        return False

    @staticmethod
    def _task_state_to_dict(state: TaskState) -> Dict[str, Any]:
        from .http_server import TaskStateResult

        return TaskStateResult.to_dict(state)

    @staticmethod
    def _task_event_to_dict(event: TaskEvent) -> Dict[str, Any]:
        from .http_server import TaskEventResult

        return TaskEventResult.to_dict(event)

    @staticmethod
    def _job_event_to_dict(event: JobEvent) -> Dict[str, Any]:
        from .http_server import JobEventResult

        return JobEventResult.to_dict(event)
