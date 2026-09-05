from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Any
from collections.abc import AsyncIterator
from typing_extensions import Self
from pydantic import BaseModel
from mindor.dsl.schema.controller import HttpServerControllerAdapterConfig, ControllerAdapterType
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.utils.transport.http_client import request_with_url
from mindor.core.utils.transport.http_request import parse_request_body, parse_options_header
from mindor.core.foundation.streaming.image import ImageStreamResource
from mindor.core.foundation.streaming.resources import StreamResource
from mindor.core.foundation.streaming.iterators import StreamIterator, StreamEncodingIterator, StreamChunkIterator
from mindor.core.utils.transport.http_stream import HttpEventStreamer
from mindor.core.controller.base import TaskState, TaskStatus, InterruptState, TaskEvent, JobEvent
from mindor.core.workflow.schema import WorkflowSchema
from mindor.core.workflow import WorkflowResolver
from mindor.core.errors import ShutdownError
from mindor.core.controller.errors import TaskNotFoundError, TaskAlreadyFinishedError, TaskCancelInProgressError
from ..base import ControllerAdapterService, register_controller_adapter
from .websocket_server import WebSocketServer
from fastapi import FastAPI, APIRouter, Request, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from PIL import Image as PILImage
import uvicorn, logging

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
    callback_url: Optional[str] = None
    callback_headers: Optional[Dict[str, str]] = None

class WorkflowResumeBody(BaseModel):
    job_id: str
    run_id: Optional[str] = None
    answer: Optional[Any] = None

class InterruptResult(BaseModel):
    job_id: str
    run_id: Optional[str] = None
    phase: Literal[ "before", "after" ]
    message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_instance(cls, instance: InterruptState) -> Self:
        return cls(
            job_id=instance.job_id,
            run_id=instance.run_id,
            phase=instance.phase,
            message=instance.message,
            metadata=instance.metadata
        )

class TaskStateResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]
    workflow_id: Optional[str] = None
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
            workflow_id=instance.workflow_id,
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
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]

class TaskSubscribedResult(BaseModel):
    task_id: str
    state: Dict[str, Any]

class TaskUnsubscribedResult(BaseModel):
    task_id: str

class TaskResumedResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]

class JobEventResult(BaseModel):
    task_id: str
    run_id: Optional[Union[str, List[str]]] = None
    workflow_id: str
    job_id: str
    job_type: str
    event: Literal[ "started", "cancelled", "completed", "failed", "routed" ]
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
            job_type=instance.job_type,
            event=instance.event,
            elapsed=instance.elapsed,
            output=instance.output,
            error=instance.error,
            next_job_id=instance.next_job_id,
        )

    @classmethod
    def to_dict(cls, instance: JobEvent) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class TaskEventResult(BaseModel):
    task_id: str
    workflow_id: Optional[str] = None
    event: Literal[ "started", "interrupted", "resumed", "cancelled", "completed", "failed" ]
    status: Literal[ "pending", "processing", "interrupted", "cancelling", "cancelled", "completed", "failed" ]
    output: Optional[Any] = None
    error: Optional[str] = None
    interrupt: Optional[InterruptResult] = None
    elapsed: Optional[float] = None
    session_id: Optional[str] = None
    metadata: Optional[Any] = None

    @classmethod
    def from_instance(cls, instance: TaskEvent) -> Self:
        return cls(
            task_id=instance.task_id,
            workflow_id=instance.workflow_id,
            event=instance.event,
            status=instance.status,
            output=instance.output,
            error=instance.error,
            interrupt=InterruptResult.from_instance(instance.interrupt) if instance.interrupt else None,
            elapsed=instance.elapsed,
            session_id=instance.session_id,
            metadata=instance.metadata,
        )

    @classmethod
    def to_dict(cls, instance: TaskEvent) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class WorkflowVariableResult(BaseModel):
    name: Optional[str]
    type: str
    is_list: bool
    subtype: Optional[str]
    format: Optional[str]
    default: Optional[Any]

    @classmethod
    def from_instance(cls, instance: WorkflowVariableConfig) -> Self:
        return cls(
            name=instance.name,
            type=instance.type,
            is_list=instance.is_list,
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
        self.websocket_server: Optional[WebSocketServer] = None

        self._task_callbacks: Dict[str, Tuple[str, Dict[str, str]]] = {}

        self._configure_server()
        self._configure_routes()

        if self.config.websocket is not False:
            self.websocket_server = WebSocketServer(self.config.websocket, self.controller, self._resolve_workflow_id)
            self.websocket_server.configure_routes(self.router)

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

            if body.callback_url and body.wait_for_completion:
                raise HTTPException(status_code=400, detail="callback_url requires wait_for_completion=false")

            if body.callback_url and body.subscribe_task:
                raise HTTPException(status_code=400, detail="callback_url and subscribe_task are mutually exclusive")

            session_id = request.query_params.get("session_id")

            if body.subscribe_task:
                if not self.websocket_server:
                    raise HTTPException(status_code=400, detail="WebSocket is disabled")
                if not session_id:
                    raise HTTPException(status_code=400, detail="session_id query parameter required when subscribe_task=true")
                if not self.websocket_server.manager.has_connection(session_id):
                    raise HTTPException(status_code=400, detail="No active WebSocket connection for session")

            try:
                state = await self.controller.run_workflow(
                    workflow_id,
                    body.input,
                    wait_for_completion=body.wait_for_completion,
                    stop_at_streaming=body.output_only,
                    session_id=body.session_id,
                    metadata=body.metadata,
                )
            except ShutdownError:
                raise HTTPException(status_code=503, detail="Service is shutting down")

            if body.callback_url:
                self._task_callbacks[state.task_id] = (
                    body.callback_url, { "Content-Type": "application/json", **(body.callback_headers or {}) },
                )

            if body.subscribe_task and session_id and self.websocket_server:
                self.websocket_server.manager.subscribe_task(session_id, state.task_id)
                state = self.controller.get_task_state(state.task_id)
                if state:
                    await self.websocket_server.notify_task_subscribed(session_id, state)

            return self._render_task_response(state, body.output_only, allow_streaming=True)

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
            body: WorkflowResumeBody = Body(...)
        ):
            try:
                state = await self.controller.resume_workflow(task_id, body.job_id, body.run_id, body.answer)
                return JSONResponse(content=TaskStateResult.to_dict(state))
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @self.router.post("/tasks/{task_id}/cancel")
        async def cancel_task(
            task_id: str,
            wait_for_completion: bool = True
        ):
            try:
                state = await self.controller.cancel_workflow(task_id, wait_for_completion=wait_for_completion)
                return JSONResponse(content=TaskStateResult.to_dict(state))
            except TaskNotFoundError as e:
                raise HTTPException(status_code=404, detail=str(e))
            except (TaskAlreadyFinishedError, TaskCancelInProgressError) as e:
                raise HTTPException(status_code=409, detail=str(e))

        @self.router.get("/health")
        async def health_check():
            if self.controller.is_shutdown_pending:
                return JSONResponse(status_code=503, content={ "status": "shutdown_pending" })

            if self.controller.is_shutting_down:
                return JSONResponse(status_code=503, content={ "status": "shutting_down" })

            return JSONResponse(content={ "status": "ok" })

    async def _start(self) -> None:
        self.controller.add_task_state_listener(self._on_task_state_change)
        self.controller.add_task_event_listener(self._on_task_event)
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
        self.controller.remove_task_event_listener(self._on_task_event)
        self.controller.remove_job_event_listener(self._on_job_event)
        if self.websocket_server:
            await self.websocket_server.dispose()

        if self.server:
            self.server.should_exit = True

        if self.daemon_task:
            await self.daemon_task

    async def _on_task_state_change(self, task_id: str, state: TaskState) -> None:
        if self.websocket_server:
            await self.websocket_server.broadcast_task_state(task_id, state)

    async def _on_task_event(self, event: TaskEvent) -> None:
        if self.websocket_server:
            await self.websocket_server.broadcast_task_event(event)

        if event.event in ("completed", "failed", "cancelled"):
            callback = self._task_callbacks.pop(event.task_id, None)

            if callback:
                await self._send_task_callback(event, *callback)

    async def _on_job_event(self, event: JobEvent) -> None:
        if self.websocket_server:
            await self.websocket_server.broadcast_job_event(event)

    async def _send_task_callback(self, event: TaskEvent, callback_url: str, headers: Dict[str, str]) -> None:
        try:
            payload = TaskEventResult.from_instance(event).model_dump(exclude_none=True, mode="json")
            await request_with_url(
                callback_url,
                method="POST",
                body=payload,
                headers=headers,
                raise_on_error=False,
            )
        except Exception:
            logging.warning("Failed to deliver task callback for %s to %s", event.task_id, callback_url, exc_info=True)

    def _resolve_workflow_id(self, workflow_id: str) -> Optional[str]:
        if workflow_id == "__default__":
            workflow_id, _ = WorkflowResolver(self.controller.workflows).resolve(workflow_id, raise_on_error=False)
        return workflow_id

    def _render_task_response(self, state: TaskState, output_only: bool, allow_streaming: bool = False) -> Response:
        if not output_only and isinstance(state.output, (StreamResource, StreamIterator, AsyncIterator)):
            raise HTTPException(status_code=400, detail="Streaming output is only allowed when output_only=true.")

        if output_only:
            return self._render_task_output(state, allow_streaming=allow_streaming)

        return self._render_task_state(state)

    def _render_task_state(self, state: TaskState) -> Response:
        return JSONResponse(content=TaskStateResult.to_dict(state))

    def _render_task_output(self, state: TaskState, allow_streaming: bool = False) -> Response:
        if state.status in (TaskStatus.PENDING, TaskStatus.PROCESSING, TaskStatus.INTERRUPTED, TaskStatus.CANCELLING):
            return JSONResponse(status_code=202, content=TaskStateResult.to_dict(state))

        if state.status == TaskStatus.STREAMING:
            if not allow_streaming:
                return JSONResponse(status_code=202, content=TaskStateResult.to_dict(state))
            return self._render_stream_output(state.output)

        if state.status == TaskStatus.CANCELLED:
            return JSONResponse(status_code=409, content=TaskStateResult.to_dict(state))

        if state.status == TaskStatus.FAILED:
            raise HTTPException(status_code=500, detail=str(state.error))

        if isinstance(state.output, PILImage.Image):
            return self._render_stream_resource(ImageStreamResource(state.output))

        if isinstance(state.output, (StreamResource, StreamIterator, AsyncIterator)):
            return self._render_stream_output(state.output)

        if isinstance(state.output, bytes):
            return Response(content=state.output, media_type="application/octet-stream")

        return JSONResponse(content=state.output)

    def _render_stream_output(self, output: Any) -> Response:
        if isinstance(output, StreamResource):
            return self._render_stream_resource(output)

        if isinstance(output, StreamEncodingIterator):
            return self._render_event_stream(output)

        return StreamingResponse(output, media_type="application/octet-stream")

    def _render_stream_resource(self, resource: StreamResource) -> Response:
        return StreamingResponse(
            resource,
            media_type=resource.content_type,
            headers=self._build_stream_resource_headers(resource),
            background=BackgroundTask(resource.close)
        )

    def _render_event_stream(self, iterator: StreamEncodingIterator) -> Response:
        return StreamingResponse(
            HttpEventStreamer(iterator).stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache"
            }
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
