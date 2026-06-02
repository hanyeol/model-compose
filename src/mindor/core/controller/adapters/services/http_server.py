from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any, Callable, get_type_hints
from collections.abc import AsyncIterator
from typing_extensions import Self
from pydantic import BaseModel, Field, ValidationError
from mindor.dsl.schema.controller import HttpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.http_response import HttpEventStreamer
from mindor.core.utils.image import ImageStreamResource
from mindor.core.utils.streaming import StreamResource, EventIteratorStreamResource
from mindor.core.controller.base import TaskState, TaskStatus, InterruptState, JobEvent
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.workflow import WorkflowResolver
from mindor.core.errors import TaskError, ShutdownError
from ..base import ControllerAdapterService, register_controller_adapter
from fastapi import FastAPI, APIRouter, Request, Body, HTTPException
from fastapi import WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from PIL import Image as PILImage
from datetime import datetime, timezone
import uvicorn, json, uuid, asyncio, inspect, functools

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class WorkflowRunBody(BaseModel):
    workflow_id: Optional[str] = None
    input: Optional[Any] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None
    wait_for_completion: bool = True
    output_only: bool = False
    subscribe_task: bool = False

class WorkflowResumeBody(BaseModel):
    job_id: str
    answer: Optional[Any] = None

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
    answer: Optional[Any] = None

class TaskGetPayload(BaseModel):
    task_id: str

class PingPayload(BaseModel):
    pass

class InterruptResult(BaseModel):
    job_id: str
    phase: Literal[ "before", "after" ]
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_instance(cls, instance: InterruptState) -> Self:
        return cls(
            job_id=instance.job_id,
            phase=instance.phase,
            message=instance.message,
            metadata=instance.metadata
        )

class TaskStateResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "completed", "failed" ]
    output: Optional[Any] = None
    error: Optional[str] = None
    interrupt: Optional[InterruptResult] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None

    @classmethod
    def from_instance(cls, instance: TaskState) -> Self:
        return cls(
            task_id=instance.task_id,
            status=instance.status,
            output=instance.output,
            error=instance.error,
            interrupt=InterruptResult.from_instance(instance.interrupt) if instance.interrupt else None,
            session_id=instance.session_id,
            metadata=instance.metadata,
        )

    @classmethod
    def to_dict(cls, instance: TaskState) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class WorkflowStartedResult(BaseModel):
    task_id: str
    workflow_id: str
    status: Literal[ "pending", "processing", "interrupted", "completed", "failed" ]

class TaskSubscribedResult(BaseModel):
    task_id: str
    state: Dict[str, Any]

class TaskUnsubscribedResult(BaseModel):
    task_id: str

class TaskResumedResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "completed", "failed" ]

class JobEventResult(BaseModel):
    task_id: str
    run_id: Optional[Union[str, List[str]]] = None
    workflow_id: str
    job_id: str
    event: Literal[ "started", "completed", "failed", "routed" ]
    elapsed: Optional[float] = None
    output: Optional[Any] = None
    error: Optional[str] = None
    next_job_id: Optional[str] = None

    @classmethod
    def from_instance(cls, instance: JobEvent) -> Self:
        return cls(
            task_id=instance.task_id,
            run_id=instance.run_id,
            workflow_id=instance.workflow_id,
            job_id=instance.job_id,
            event=instance.event,
            elapsed=instance.elapsed,
            output=instance.output,
            error=instance.error,
            next_job_id=instance.next_job_id,
        )

    @classmethod
    def to_dict(cls, instance: JobEvent) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class WorkflowVariableResult(BaseModel):
    name: Optional[str]
    type: str
    subtype: Optional[str]
    format: Optional[str]
    default: Optional[Any]

    @classmethod
    def from_instance(cls, instance: WorkflowVariableConfig) -> Self:
        return cls(
            name=instance.name,
            type=instance.type,
            subtype=instance.subtype,
            format=instance.format,
            default=instance.default
        )

class WorkflowVariableGroupResult(BaseModel):
    name: Optional[str]
    variables: List[WorkflowVariableResult]
    repeat_count: int

    @classmethod
    def from_instance(cls, instance: WorkflowVariableGroupConfig) -> Self:
        return cls(
            name=instance.name,
            variables=[ WorkflowVariableResult.from_instance(variable) for variable in instance.variables ],
            repeat_count=instance.repeat_count
        )

class WorkflowSimpleResult(BaseModel):
    workflow_id: str
    title: Optional[str] = None
    default: Optional[bool] = None

    @classmethod
    def from_instance(cls, instance: WorkflowSchema) -> Self:
        return cls(
            workflow_id=instance.workflow_id,
            title=instance.title,
            default=instance.default or None
        )

    @classmethod
    def to_dict(cls, instance: WorkflowSchema) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class WorkflowSchemaResult(BaseModel):
    workflow_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    input: List[WorkflowVariableResult]
    output: List[Union[WorkflowVariableResult, WorkflowVariableGroupResult]]
    default: Optional[bool] = None

    @classmethod
    def from_instance(cls, instance: WorkflowSchema) -> Self:
        return cls(
            workflow_id=instance.workflow_id,
            title=instance.title,
            description=instance.description,
            input=[ cls._to_variable_result(variable) for variable in instance.input ],
            output=[ cls._to_variable_result(variable) for variable in instance.output ],
            default=instance.default or None
        )

    @classmethod
    def to_dict(cls, instance: WorkflowSchema) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

    @classmethod
    def _to_variable_result(cls, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig]) -> Union[WorkflowVariableResult, WorkflowVariableGroupResult]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            return WorkflowVariableGroupResult.from_instance(variable)
        return WorkflowVariableResult.from_instance(variable)

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

    def has_connection(self, client_id: str) -> bool:
        return client_id in self._connections

    async def send_message(self, client_id: str, message: WebSocketMessage) -> None:
        websocket = self._connections.get(client_id)
        if not websocket:
            return

        await websocket.send_text(self._serialize_message(message))

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

    def has_task_subscribers(self, task_id: str) -> bool:
        return bool(self._task_subscribers.get(task_id))

    def _serialize_message(self, message: WebSocketMessage) -> str:
        return json.dumps(message.model_dump(exclude_none=True, mode="json"), ensure_ascii=False, default=str)

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

@register_controller_adapter(ControllerAdapterType.HTTP_SERVER)
class HttpServerControllerAdapterService(ControllerAdapterService):
    def __init__(
        self,
        config: HttpServerControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool
    ):
        super().__init__(config, controller, daemon)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.http_router: APIRouter = APIRouter()
        self.websocket_manager: WebSocketManager = WebSocketManager()
        self.websocket_router: WebSocketRouter = WebSocketRouter()

        self._configure_server()
        self._configure_http_routes()
        if self.config.websocket is not False:
            self._configure_websocket_routes()
        self.app.include_router(self.http_router, prefix=self.config.base_path or "")

    def _configure_server(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[self.config.origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _configure_http_routes(self) -> None:
        @self.http_router.get("/workflows")
        async def get_workflow_list(
            include_schema: bool = False
        ):
            if include_schema:
                return self._render_workflow_schemas(self.controller.workflow_schemas)

            return self._render_workflow_list(self.controller.workflow_schemas)

        @self.http_router.get("/workflows/{workflow_id}/schema")
        async def get_workflow_schema(
            workflow_id: str
        ):
            if workflow_id not in self.controller.workflow_schemas:
                raise HTTPException(status_code=404, detail="Workflow not found.")

            return self._render_workflow_schema(self.controller.workflow_schemas[workflow_id])

        @self.http_router.post("/workflows/runs")
        async def run_workflow(
            request: Request
        ):
            content_type, _ = parse_options_header(request.headers, "Content-Type")
            if content_type not in ("application/json", "multipart/form-data", "application/x-www-form-urlencoded"):
                raise HTTPException(status_code=400, detail="Missing or empty Content-Type header." if not content_type else f"Unsupported Content-Type: {content_type}")

            try:
                body = WorkflowRunBody(**await parse_request_body(request, content_type, nested=True))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

            workflow_id = self._resolve_workflow_id(body.workflow_id or "__default__")
            if not workflow_id or not self.controller.is_workflow_available(workflow_id):
                raise HTTPException(status_code=404, detail=f"Workflow '{body.workflow_id or '__default__'}' not found.")

            if body.subscribe_task and body.wait_for_completion:
                raise HTTPException(status_code=400, detail="subscribe_task=true requires wait_for_completion=false")

            if body.output_only and not body.wait_for_completion:
                raise HTTPException(status_code=400, detail="output_only=true requires wait_for_completion=true.")

            session_id = request.query_params.get("session_id")

            if body.subscribe_task:
                if not session_id:
                    raise HTTPException(status_code=400, detail="session_id query parameter required when subscribe_task=true")
                if not self.websocket_manager.has_connection(session_id):
                    raise HTTPException(status_code=400, detail="No active WebSocket connection for session")

            try:
                state = await self.controller.run_workflow(
                    workflow_id, body.input, body.wait_for_completion,
                    session_id=body.session_id, metadata=body.metadata,
                )
            except ShutdownError:
                raise HTTPException(status_code=503, detail="Service is shutting down")

            if body.subscribe_task and session_id:
                self.websocket_manager.subscribe_task(session_id, state.task_id)
                state = self.controller.get_task_state(state.task_id)
                if state:
                    await self.websocket_manager.send_message(session_id, WebSocketMessage(
                        type="task_state",
                        data=TaskStateResult.to_dict(state),
                    ))

            return self._render_task_response(state, body.output_only)

        @self.http_router.get("/tasks/{task_id}")
        async def get_task_state(
            task_id: str,
            output_only: bool = False
        ):
            state = self.controller.get_task_state(task_id)

            if not state:
                raise HTTPException(status_code=404, detail="Task not found.")

            return self._render_task_response(state, output_only)

        @self.http_router.post("/tasks/{task_id}/resume")
        async def resume_task(
            task_id: str,
            body: WorkflowResumeBody = Body(...)
        ):
            try:
                state = await self.controller.resume_workflow(task_id, body.job_id, body.answer)
                return JSONResponse(content=TaskStateResult.to_dict(state))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.http_router.get("/health")
        async def health_check():
            return JSONResponse(content={ "status": "ok" })

    def _configure_websocket_routes(self) -> None:
        @self.http_router.websocket(self.config.websocket.path)
        async def serve_websocket(
            websocket: WebSocket,
            session: Optional[str] = None,
            task: Optional[str] = None,
        ):
            if self.config.websocket.max_connection_count and len(self.websocket_manager._connections) >= self.config.websocket.max_connection_count:
                await websocket.close(code=4429, reason="Too many connections")
                return

            client_id = session if session else str(uuid.uuid4())
            accepted = await self.websocket_manager.accept(client_id, websocket)
            if not accepted:
                return

            if task:
                state = self.controller.get_task_state(task)
                if state:
                    self.websocket_manager.subscribe_task(client_id, task)
                    await self.websocket_manager.send_message(client_id, WebSocketMessage(
                        type="task_subscribed",
                        data=TaskSubscribedResult(
                            task_id=task,
                            state=TaskStateResult.to_dict(state),
                        ).model_dump(exclude_none=True),
                    ))
                else:
                    await self.websocket_manager.send_message(client_id, WebSocketMessage(
                        type="error",
                        data={
                            "code": "TASK_NOT_FOUND",
                            "message": f"Task '{task}' not found",
                        },
                    ))

            try:
                while True:
                    message_text = await websocket.receive_text()
                    try:
                        message = WebSocketMessage(**json.loads(message_text))
                    except json.JSONDecodeError:
                        await self.websocket_manager.send_error(client_id, "INVALID_REQUEST", "Invalid JSON")
                        continue
                    except Exception as e:
                        await self.websocket_manager.send_error(client_id, "INVALID_REQUEST", f"Invalid message: {e}")
                        continue

                    handler = self.websocket_router.resolve(message.type)
                    if handler:
                        try:
                            await handler(client_id, message.id, message.data)
                        except ValidationError as e:
                            await self.websocket_manager.send_error(client_id, "INVALID_REQUEST", f"Invalid data: {e}", message.id)
                        except Exception as e:
                            await self.websocket_manager.send_error(client_id, "INTERNAL_ERROR", str(e), message.id)
                    else:
                        await self.websocket_manager.send_error(client_id, "INVALID_REQUEST", f"Unknown message type: {message.type}", message.id)
            finally:
                await self.websocket_manager.close(client_id)

        @self.websocket_router.handler("run_workflow")
        async def run_workflow(client_id: str, message_id: Optional[str], payload: WorkflowRunPayload) -> None:
            workflow_id = self._resolve_workflow_id(payload.workflow_id or "__default__")

            if not workflow_id or not self.controller.is_workflow_available(workflow_id):
                await self.websocket_manager.send_error(client_id, "WORKFLOW_NOT_FOUND", f"Workflow '{payload.workflow_id or '__default__'}' not found", message_id)
                return

            state = await self.controller.run_workflow(
                workflow_id, payload.input, wait_for_completion=False,
                session_id=payload.session_id, metadata=payload.metadata,
            )

            if payload.subscribe_task:
                self.websocket_manager.subscribe_task(client_id, state.task_id)

            await self.websocket_manager.send_message(client_id, WebSocketMessage(
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
                    await self.websocket_manager.send_message(client_id, WebSocketMessage(
                        type="task_state",
                        data=TaskStateResult.to_dict(state)
                    ))

        @self.websocket_router.handler("subscribe_task")
        async def subscribe_task(client_id: str, message_id: Optional[str], payload: TaskSubscribePayload) -> None:
            state = self.controller.get_task_state(payload.task_id)
            if not state:
                await self.websocket_manager.send_error(client_id, "TASK_NOT_FOUND", f"Task '{payload.task_id}' not found", message_id)
                return

            self.websocket_manager.subscribe_task(client_id, payload.task_id)

            await self.websocket_manager.send_message(client_id, WebSocketMessage(
                type="task_subscribed",
                id=message_id,
                data=TaskSubscribedResult(
                    task_id=payload.task_id,
                    state=TaskStateResult.to_dict(state),
                ).model_dump(exclude_none=True),
            ))

        @self.websocket_router.handler("unsubscribe_task")
        async def unsubscribe_task(client_id: str, message_id: Optional[str], payload: TaskUnsubscribePayload) -> None:
            self.websocket_manager.unsubscribe_task(client_id, payload.task_id)

            await self.websocket_manager.send_message(client_id, WebSocketMessage(
                type="task_unsubscribed",
                id=message_id,
                data=TaskUnsubscribedResult(
                    task_id=payload.task_id
                ).model_dump(exclude_none=True),
            ))

        @self.websocket_router.handler("resume_task")
        async def resume_task(client_id: str, message_id: Optional[str], payload: TaskResumePayload) -> None:
            try:
                state = await self.controller.resume_workflow(payload.task_id, payload.job_id, payload.answer)
                await self.websocket_manager.send_message(client_id, WebSocketMessage(
                    type="task_resumed",
                    id=message_id,
                    data=TaskResumedResult(
                        task_id=payload.task_id,
                        status=state.status,
                    ).model_dump(exclude_none=True),
                ))
            except TaskError as e:
                await self.websocket_manager.send_error(client_id, e.code, str(e), message_id)

        @self.websocket_router.handler("get_task")
        async def get_task(client_id: str, message_id: Optional[str], payload: TaskGetPayload) -> None:
            state = self.controller.get_task_state(payload.task_id)
            if not state:
                await self.websocket_manager.send_error(client_id, "TASK_NOT_FOUND", f"Task '{payload.task_id}' not found", message_id)
                return

            await self.websocket_manager.send_message(client_id, WebSocketMessage(
                type="task_state",
                id=message_id,
                data=TaskStateResult.to_dict(state)
            ))

        @self.websocket_router.handler("ping")
        async def ping(client_id: str, message_id: Optional[str], payload: PingPayload) -> None:
            await self.websocket_manager.send_message(client_id, WebSocketMessage(
                type="pong",
                id=message_id,
            ))

    async def _start(self) -> None:
        self.controller.add_task_state_listener(self._on_task_state_change)
        self.controller.add_job_event_listener(self._on_job_event)

        await super()._start()

    async def _serve(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))

        try:
            await self.server.serve()
        finally:
            self.server = None

    async def _shutdown(self) -> None:
        self.controller.remove_task_state_listener(self._on_task_state_change)
        self.controller.remove_job_event_listener(self._on_job_event)
        await self.websocket_manager.dispose()

        if self.server:
            self.server.should_exit = True

    async def _on_task_state_change(self, task_id: str, state: TaskState) -> None:
        if self.websocket_manager.has_task_subscribers(task_id):
            await self.websocket_manager.broadcast_task_message(
                task_id,
                WebSocketMessage(
                    type="task_state",
                    data=TaskStateResult.to_dict(state)
                )
            )

    async def _on_job_event(self, event: JobEvent) -> None:
        if self.websocket_manager.has_task_subscribers(event.task_id):
            await self.websocket_manager.broadcast_task_message(
                event.task_id,
                WebSocketMessage(
                    type="job_event",
                    data=JobEventResult.to_dict(event)
                )
            )

    def _resolve_workflow_id(self, workflow_id: str) -> Optional[str]:
        if workflow_id == "__default__":
            workflow_id, _ = WorkflowResolver(self.controller.workflows).resolve(workflow_id, raise_on_error=False)
        return workflow_id

    def _render_task_response(self, state: TaskState, output_only: bool) -> Response:
        if not output_only and isinstance(state.output, (StreamResource, AsyncIterator)):
            raise HTTPException(status_code=400, detail="Streaming output is only allowed when output_only=true.")

        if output_only:
            return self._render_task_output(state)

        return self._render_task_state(state)

    def _render_task_state(self, state: TaskState) -> Response:
        return JSONResponse(content=TaskStateResult.to_dict(state))

    def _render_task_output(self, state: TaskState) -> Response:
        if state.status in [ TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.INTERRUPTED ]:
            return JSONResponse(status_code=202, content=TaskStateResult.to_dict(state))

        if state.status == TaskStatus.FAILED:
            raise HTTPException(status_code=500, detail=str(state.error))

        if isinstance(state.output, PILImage.Image):
            return self._render_stream_resource(ImageStreamResource(state.output))

        if isinstance(state.output, EventIteratorStreamResource):
            return self._render_http_event_stream(state.output)

        if isinstance(state.output, StreamResource):
            return self._render_stream_resource(state.output)

        if isinstance(state.output, AsyncIterator):
            return StreamingResponse(state.output, media_type="application/octet-stream")

        if isinstance(state.output, bytes):
            return Response(content=state.output, media_type="application/octet-stream")

        return JSONResponse(content=state.output)

    def _render_http_event_stream(self, resource: StreamResource) -> Response:
        format = resource.format if isinstance(resource, EventIteratorStreamResource) else None
        return StreamingResponse(
            HttpEventStreamer(resource, format).stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache"
            }
        )

    def _render_stream_resource(self, resource: StreamResource) -> Response:
        return StreamingResponse(
            resource,
            media_type=resource.content_type,
            headers=self._build_stream_resource_headers(resource),
            background=BackgroundTask(resource.close)
        )

    def _build_stream_resource_headers(self, resource: StreamResource) -> Dict[str, str]:
        headers: Dict[str, str] = { "Cache-Control": "no-cache" }

        if resource.filename:
            filename = resource.filename.replace('"', '\\"')
            headers["Content-Disposition"] = f'attachment; filename="{filename}"'

        return headers

    def _render_workflow_list(self, workflows: Dict[str, WorkflowSchema]) -> Response:
        return JSONResponse(content=[
            WorkflowSimpleResult.to_dict(workflow) for workflow in workflows.values()
        ])

    def _render_workflow_schemas(self, workflows: Dict[str, WorkflowSchema]) -> Response:
        return JSONResponse(content=[
            WorkflowSchemaResult.to_dict(workflow) for workflow in workflows.values()
        ])

    def _render_workflow_schema(self, workflow: WorkflowSchema) -> Response:
        return JSONResponse(content=WorkflowSchemaResult.to_dict(workflow))
