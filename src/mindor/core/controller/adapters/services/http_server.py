from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from typing_extensions import Self
from pydantic import BaseModel
from mindor.dsl.schema.controller import HttpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.http_response import HttpEventStreamer
from mindor.core.utils.image import ImageStreamResource
from mindor.core.utils.streaming import StreamResource, EventIteratorStreamResource
from mindor.core.controller.base import TaskState, TaskStatus, InterruptState, JobEvent
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.workflow import WorkflowResolver
from mindor.core.errors import ShutdownError, TaskError
from ..base import ControllerAdapterService, register_controller_adapter
from fastapi import FastAPI, APIRouter, Request, Body, HTTPException
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from PIL import Image as PILImage
from datetime import datetime, timezone
import uvicorn, json, uuid, asyncio

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class WorkflowRunRequestBody(BaseModel):
    workflow_id: Optional[str] = None
    input: Optional[Any] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None
    wait_for_completion: bool = True
    output_only: bool = False
    subscribe_task: bool = False

class WorkflowResumeRequestBody(BaseModel):
    job_id: str
    answer: Optional[Any] = None

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

class TaskResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "completed", "failed" ]
    output: Optional[Any] = None
    error: Optional[Any] = None
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
            metadata=instance.metadata,
            session_id=instance.session_id
        )

    @classmethod
    def to_dict(cls, instance: TaskState) -> Dict[str, Any]:
        return {
            **cls.from_instance(instance).model_dump(exclude_none=True),
            "metadata": instance.metadata
        }

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

class WebSocketConnectionManager:
    def __init__(self):
        self._connections: Dict[str, WebSocket] = {}
        self._task_subscriptions: Dict[str, Set[str]] = {}
        self._client_subscriptions: Dict[str, Set[str]] = {}

    async def connect(self, client_id: str, websocket: WebSocket) -> bool:
        if client_id in self._connections:
            await websocket.close(code=4409, reason="Session already connected")
            return False
        await websocket.accept()
        self._connections[client_id] = websocket
        self._client_subscriptions[client_id] = set()
        return True

    async def disconnect(self, client_id: str) -> None:
        subscriptions = self._client_subscriptions.pop(client_id, None)
        if subscriptions:
            for task_id in subscriptions:
                subsription = self._task_subscriptions.get(task_id)
                if subsription is not None:
                    subsription.discard(client_id)
                    if not subsription:
                        self._task_subscriptions.pop(task_id, None)
        self._connections.pop(client_id, None)

    async def disconnect_all(self) -> None:
        for client_id in list(self._connections.keys()):
            await self.disconnect(client_id)

    def has_connection(self, client_id: str) -> bool:
        return client_id in self._connections

    async def send_message(self, client_id: str, message: dict) -> bool:
        websocket = self._connections.get(client_id)
        if not websocket:
            return False
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            await self.disconnect(client_id)
            return False

    async def broadcast_to_task_subscribers(self, task_id: str, message: dict) -> None:
        subscriber_ids = self._task_subscriptions.get(task_id) or []
        message_text = json.dumps(message, ensure_ascii=False, default=str)
        tasks = []
        for client_id in list(subscriber_ids):
            websocket = self._connections.get(client_id)
            if websocket:
                tasks.append(self._send_raw(client_id, websocket, message_text))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def has_task_subscribers(self, task_id: str) -> bool:
        return bool(self._task_subscriptions.get(task_id))

    def subscribe_to_task(self, client_id: str, task_id: str) -> None:
        if task_id not in self._task_subscriptions:
            self._task_subscriptions[task_id] = set()
        self._task_subscriptions[task_id].add(client_id)
        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].add(task_id)

    def unsubscribe_from_task(self, client_id: str, task_id: str) -> None:
        if task_id in self._task_subscriptions:
            self._task_subscriptions[task_id].discard(client_id)
            if not self._task_subscriptions[task_id]:
                del self._task_subscriptions[task_id]
        if client_id in self._client_subscriptions:
            self._client_subscriptions[client_id].discard(task_id)

    async def _send_raw(self, client_id: str, websocket: WebSocket, text: str) -> None:
        try:
            await websocket.send_text(text)
        except Exception:
            await self.disconnect(client_id)

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
        self.router: APIRouter = APIRouter()
        self.websocket_manager: WebSocketConnectionManager = WebSocketConnectionManager()

        self._configure_server()
        self._configure_routes()
        if self.config.websocket is not False:
            self._configure_websocket()
        self.app.include_router(self.router, prefix=self.config.base_path or "")

    def _configure_server(self) -> None:
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=[self.config.origins],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _configure_routes(self) -> None:
        @self.router.get("/workflows")
        async def get_workflow_list(
            include_schema: bool = False
        ):
            if include_schema:
                return self._render_workflow_schemas(self.controller.workflow_schemas)

            return self._render_workflow_list(self.controller.workflow_schemas)

        @self.router.get("/workflows/{workflow_id}/schema")
        async def get_workflow_schema(
            workflow_id: str
        ):
            if workflow_id not in self.controller.workflow_schemas:
                raise HTTPException(status_code=404, detail="Workflow not found.")

            return self._render_workflow_schema(self.controller.workflow_schemas[workflow_id])

        @self.router.post("/workflows/runs")
        async def run_workflow(
            request: Request
        ):
            return await self._handle_workflow_run_request(request)

        @self.router.get("/tasks/{task_id}")
        async def get_task_state(
            task_id: str,
            output_only: bool = False
        ):
            state = self.controller.get_task_state(task_id)

            if not state:
                raise HTTPException(status_code=404, detail="Task not found.")

            return self._render_task_response(state, output_only)

        @self.router.post("/tasks/{task_id}/resume")
        async def resume_task(
            task_id: str,
            body: WorkflowResumeRequestBody = Body(...)
        ):
            try:
                state = await self.controller.resume_workflow(task_id, body.job_id, body.answer)
                return JSONResponse(content=TaskResult.to_dict(state))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.get("/health")
        async def health_check():
            return JSONResponse(content={ "status": "ok" })

    def _configure_websocket(self) -> None:
        @self.router.websocket(self.config.websocket.path)
        async def websocket_endpoint(
            websocket: WebSocket,
            session: Optional[str] = None,
            task: Optional[str] = None,
        ):
            if self.config.websocket.max_connections and len(self.websocket_manager._connections) >= self.config.websocket.max_connections:
                await websocket.close(code=4429, reason="Too many connections")
                return

            client_id = session if session else str(uuid.uuid4())

            connected = await self.websocket_manager.connect(client_id, websocket)
            if not connected:
                return

            if task:
                task_state = self.controller.get_task_state(task)
                if task_state:
                    self.websocket_manager.subscribe_to_task(client_id, task)
                    await self.websocket_manager.send_message(client_id, {
                        "type": "task_subscribed",
                        "data": {
                            "task_id": task,
                            "current_state": self._serialize_task_state(task, task_state)
                        }
                    })
                else:
                    await self.websocket_manager.send_message(client_id, {
                        "type": "error",
                        "data": {
                            "code": "TASK_NOT_FOUND",
                            "message": f"Task '{task}' not found"
                        }
                    })

            try:
                while True:
                    raw_message = await websocket.receive_text()
                    await self._handle_websocket_message(client_id, raw_message)
            except WebSocketDisconnect:
                await self.websocket_manager.disconnect(client_id)
            except Exception as e:
                await self._websocket_send_error(client_id, "INTERNAL_ERROR", str(e))
                await self.websocket_manager.disconnect(client_id)

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
        await self.websocket_manager.disconnect_all()

        if self.server:
            self.server.should_exit = True

    async def _handle_workflow_run_request(self, request: Request) -> Response:
        body = await self._parse_workflow_run_body(request)

        workflow_id = self._resolve_workflow_id(body.workflow_id or "__default__")

        if not workflow_id or not self.controller.is_workflow_available(workflow_id):
            raise HTTPException(status_code=404, detail=f"Workflow '{body.workflow_id or '__default__'}' not found.")

        if body.subscribe_task and body.wait_for_completion:
            raise HTTPException(status_code=400, detail="subscribe_task=true requires wait_for_completion=false")

        session_id = request.query_params.get("session_id")

        if body.subscribe_task:
            if not session_id:
                raise HTTPException(status_code=400, detail="session_id query parameter required when subscribe_task=true")
            if not self.websocket_manager.has_connection(session_id):
                raise HTTPException(status_code=400, detail="No active WebSocket connection for session")

        try:
            state = await self.controller.run_workflow(
                workflow_id,
                body.input,
                body.wait_for_completion,
                session_id=body.session_id,
                metadata=body.metadata
            )
        except ShutdownError:
            raise HTTPException(status_code=503, detail="Service is shutting down")

        if body.subscribe_task and session_id:
            self.websocket_manager.subscribe_to_task(session_id, state.task_id)
            current = self.controller.get_task_state(state.task_id)
            if current:
                await self.websocket_manager.send_message(session_id, {
                    "type": "task_state",
                    "data": self._serialize_task_state(state.task_id, current)
                })

        if body.output_only and not body.wait_for_completion:
            raise HTTPException(status_code=400, detail="output_only requires wait_for_completion=true.")

        return self._render_task_response(state, body.output_only)

    async def _parse_workflow_run_body(self, request: Request) -> WorkflowRunRequestBody:
        content_type, _ = parse_options_header(request.headers, "Content-Type")

        if content_type not in [ "application/json", "multipart/form-data", "application/x-www-form-urlencoded" ]:
            if not content_type:
                raise HTTPException(status_code=400, detail="Missing or empty Content-Type header.")
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported Content-Type: {content_type}")

        try:
            return WorkflowRunRequestBody(**await parse_request_body(request, content_type, nested=True))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    def _resolve_workflow_id(self, workflow_id: str) -> Optional[str]:
        if workflow_id == "__default__":
            resolved_id, _ = WorkflowResolver(self.controller.workflows).resolve(workflow_id, raise_on_error=False)
            return resolved_id
        return workflow_id

    async def _on_task_state_change(self, task_id: str, state: TaskState) -> None:
        if self.websocket_manager.has_task_subscribers(task_id):
            await self.websocket_manager.broadcast_to_task_subscribers(
                task_id,
                {
                    "type": "task_state",
                    "data": self._serialize_task_state(task_id, state)
                }
            )

    async def _on_job_event(self, event: JobEvent) -> None:
        if self.websocket_manager.has_task_subscribers(event.task_id):
            await self.websocket_manager.broadcast_to_task_subscribers(
                event.task_id,
                {
                    "type": "job_event",
                    "data": self._serialize_job_event(event)
                }
            )

    def _serialize_task_state(self, task_id: str, state: TaskState) -> dict:
        result = {
            "task_id": task_id,
            "status": state.status.value if hasattr(state.status, 'value') else state.status,
            "output": None,
            "error": None,
            "interrupt": None,
            "session_id": state.session_id,
            "metadata": state.metadata,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if state.status == TaskStatus.COMPLETED and state.output is not None:
            try:
                json.dumps(state.output)
                result["output"] = state.output
            except (TypeError, ValueError):
                result["output"] = None
        if state.error:
            result["error"] = str(state.error)
        if state.interrupt:
            result["interrupt"] = {
                "job_id": state.interrupt.job_id,
                "phase": state.interrupt.phase,
                "message": state.interrupt.message,
                "metadata": state.interrupt.metadata,
            }
        return result

    def _serialize_job_event(self, event: JobEvent) -> dict:
        result = {
            "task_id": event.task_id,
            "run_id": event.run_id,
            "workflow_id": event.workflow_id,
            "job_id": event.job_id,
            "event": event.event,
            "elapsed": None,
            "output": None,
            "error": None,
            "next_job_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        if event.elapsed is not None:
            result["elapsed"] = event.elapsed
        if event.output is not None:
            try:
                json.dumps(event.output)
                result["output"] = event.output
            except (TypeError, ValueError):
                result["output"] = None
        if event.error:
            result["error"] = str(event.error)
        if event.next_job_id:
            result["next_job_id"] = event.next_job_id
        return result

    async def _handle_websocket_message(self, client_id: str, raw: str) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", "Invalid JSON")
            return

        message_type = message.get("type")
        message_id = message.get("id")
        data = message.get("data") or {}

        handlers = {
            "run_workflow": self._websocket_run_workflow,
            "subscribe_task": self._websocket_subscribe_task,
            "unsubscribe_task": self._websocket_unsubscribe_task,
            "resume_task": self._websocket_resume_task,
            "get_task": self._websocket_get_task,
            "ping": self._websocket_ping,
        }

        handler = handlers.get(message_type)
        if handler:
            try:
                await handler(client_id, message_id, data)
            except Exception as e:
                await self._websocket_send_error(client_id, "INTERNAL_ERROR", str(e), message_id)
        else:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", f"Unknown message type: {message_type}", message_id)

    async def _websocket_run_workflow(self, client_id: str, message_id: str, data: dict) -> None:
        workflow_id = data.get("workflow_id", "__default__")
        input_data = data.get("input")
        metadata = data.get("metadata")
        session_id = data.get("session_id")
        subscribe_task = data.get("subscribe_task", True)

        workflow_id = self._resolve_workflow_id(workflow_id)

        if not workflow_id or not self.controller.is_workflow_available(workflow_id):
            await self._websocket_send_error(client_id, "WORKFLOW_NOT_FOUND", f"Workflow '{workflow_id}' not found", message_id)
            return

        state = await self.controller.run_workflow(workflow_id, input_data, wait_for_completion=False, session_id=session_id, metadata=metadata)

        if subscribe_task:
            self.websocket_manager.subscribe_to_task(client_id, state.task_id)

        await self.websocket_manager.send_message(client_id, {
            "type": "workflow_started",
            "id": message_id,
            "data": {
                "task_id": state.task_id,
                "workflow_id": workflow_id,
                "status": state.status.value if hasattr(state.status, 'value') else state.status
            }
        })

        if subscribe_task:
            current_state = self.controller.get_task_state(state.task_id)
            if current_state and current_state.status != state.status:
                await self.websocket_manager.send_message(client_id, {
                    "type": "task_state",
                    "data": self._serialize_task_state(state.task_id, current_state)
                })

    async def _websocket_subscribe_task(self, client_id: str, message_id: str, data: dict) -> None:
        task_id = data.get("task_id")
        if not task_id:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", "Missing required field: task_id", message_id)
            return

        task_state = self.controller.get_task_state(task_id)
        if not task_state:
            await self._websocket_send_error(client_id, "TASK_NOT_FOUND", f"Task '{task_id}' not found", message_id)
            return

        self.websocket_manager.subscribe_to_task(client_id, task_id)

        await self.websocket_manager.send_message(client_id, {
            "type": "task_subscribed",
            "id": message_id,
            "data": {
                "task_id": task_id,
                "current_state": self._serialize_task_state(task_id, task_state)
            }
        })

    async def _websocket_unsubscribe_task(self, client_id: str, message_id: str, data: dict) -> None:
        task_id = data.get("task_id")
        if not task_id:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", "Missing required field: task_id", message_id)
            return

        self.websocket_manager.unsubscribe_from_task(client_id, task_id)

        await self.websocket_manager.send_message(client_id, {
            "type": "task_unsubscribed",
            "id": message_id,
            "data": {"task_id": task_id}
        })

    async def _websocket_resume_task(self, client_id: str, message_id: str, data: dict) -> None:
        task_id = data.get("task_id")
        job_id = data.get("job_id")

        if not task_id or not job_id:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", "Missing required fields: task_id, job_id", message_id)
            return

        answer = data.get("answer")

        try:
            state = await self.controller.resume_workflow(task_id, job_id, answer)
            await self.websocket_manager.send_message(client_id, {
                "type": "task_resumed",
                "id": message_id,
                "data": {
                    "task_id": task_id,
                    "status": state.status.value if hasattr(state.status, 'value') else state.status
                }
            })
        except TaskError as e:
            await self._websocket_send_error(client_id, e.code, str(e), message_id)

    async def _websocket_get_task(self, client_id: str, message_id: str, data: dict) -> None:
        task_id = data.get("task_id")
        if not task_id:
            await self._websocket_send_error(client_id, "INVALID_REQUEST", "Missing required field: task_id", message_id)
            return

        task_state = self.controller.get_task_state(task_id)
        if not task_state:
            await self._websocket_send_error(client_id, "TASK_NOT_FOUND", f"Task '{task_id}' not found", message_id)
            return

        await self.websocket_manager.send_message(client_id, {
            "type": "task_state",
            "id": message_id,
            "data": self._serialize_task_state(task_id, task_state)
        })

    async def _websocket_ping(self, client_id: str, message_id: str, data: dict) -> None:
        await self.websocket_manager.send_message(client_id, {
            "type": "pong",
            "id": message_id,
            "data": {"timestamp": datetime.now(timezone.utc).isoformat()}
        })

    async def _websocket_send_error(self, client_id: str, code: str, message: str, message_id: str = None) -> None:
        payload = {"type": "error", "data": {"code": code, "message": message}}
        if message_id:
            payload["id"] = message_id
        await self.websocket_manager.send_message(client_id, payload)

    def _render_task_response(self, state: TaskState, output_only: bool) -> Response:
        if not output_only and isinstance(state.output, (StreamResource, AsyncIterator)):
            raise HTTPException(status_code=400, detail="Streaming output is only allowed when output_only=true.")

        if output_only:
            return self._render_task_output(state)

        return self._render_task_state(state)

    def _render_task_state(self, state: TaskState) -> Response:
        return JSONResponse(content=TaskResult.to_dict(state))

    def _render_task_output(self, state: TaskState) -> Response:
        if state.status in [ TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.INTERRUPTED ]:
            return JSONResponse(status_code=202, content=TaskResult.to_dict(state))

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
