from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, AsyncIterable, Any
from types import AsyncGeneratorType
from typing_extensions import Self
from pydantic import BaseModel
from mindor.dsl.schema.controller import HttpServerControllerAdapterConfig, ControllerAdapterType
from mindor.core.errors import ShutdownError
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.http_response import HttpEventStreamer
from mindor.core.utils.http_client import HttpEventStreamResource
from mindor.core.utils.image import ImageStreamResource
from mindor.core.utils.streaming import StreamResource
from mindor.core.controller.base import TaskState, TaskStatus, InterruptState
from mindor.core.workflow.schema import WorkflowSchema
from ..base import ControllerAdapterService, register_controller_adapter
from fastapi import FastAPI, APIRouter, Request, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from PIL import Image as PILImage
import uvicorn

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class WorkflowRunRequestBody(BaseModel):
    workflow_id: Optional[str] = None
    input: Optional[Any] = None
    wait_for_completion: bool = True
    output_only: bool = False

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

    @classmethod
    def from_instance(cls, instance: TaskState) -> Self:
        return cls(
            task_id=instance.task_id,
            status=instance.status,
            output=instance.output,
            error=instance.error,
            interrupt=InterruptResult.from_instance(instance.interrupt) if instance.interrupt else None
        )

    @classmethod
    def to_dict(cls, instance: TaskState) -> Dict[str, Any]:
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

    @classmethod
    def from_instance(cls, instance: WorkflowVariableGroupConfig) -> Self:
        return cls(
            name=instance.name,
            variables=[ WorkflowVariableResult.from_instance(variable) for variable in instance.variables ]
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

        self._configure_server()
        self._configure_routes()
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
        if self.server:
            self.server.should_exit = True

    async def _handle_workflow_run_request(self, request: Request) -> Response:
        body = await self._parse_workflow_run_body(request)

        workflow_id = body.workflow_id or "__default__"

        if workflow_id not in self.controller.workflow_schemas:
            raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found.")

        try:
            state = await self.controller.run_workflow(workflow_id, body.input, body.wait_for_completion)
        except ShutdownError:
            raise HTTPException(status_code=503, detail="Service is shutting down")

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

    def _render_task_response(self, state: TaskState, output_only: bool) -> Response:
        if not output_only and isinstance(state.output, (StreamResource, AsyncGeneratorType)):
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

        if isinstance(state.output, (HttpEventStreamResource, AsyncIterator)):
            return self._render_async_iterator(state.output)

        if isinstance(state.output, StreamResource):
            return self._render_stream_resource(state.output)

        if isinstance(state.output, bytes):
            return Response(content=state.output, media_type="application/octet-stream")

        return JSONResponse(content=state.output)

    def _render_async_iterator(self, iterator: AsyncIterable[Any]) -> Response:
        return StreamingResponse(
            HttpEventStreamer(iterator).stream(),
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
