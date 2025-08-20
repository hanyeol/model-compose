from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, AsyncIterator, AsyncIterable, Any
from types import AsyncGeneratorType
from typing_extensions import Self
from pydantic import BaseModel
from mindor.dsl.schema.controller import HttpServerControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.listener import ListenerConfig
from mindor.dsl.schema.gateway import GatewayConfig
from mindor.dsl.schema.logger import LoggerConfig
from mindor.dsl.schema.workflow import WorkflowConfig, WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.http_response import HttpEventStreamer
from mindor.core.utils.http_client import HttpEventStreamResource
from mindor.core.utils.streaming import StreamResource
from ..base import ControllerService, ControllerType, WorkflowSchema, TaskState, TaskStatus, register_controller
from fastapi import FastAPI, APIRouter, Request, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
import uvicorn

class WorkflowTaskRequestBody(BaseModel):
    workflow_id: Optional[str] = None
    input: Optional[Any] = None
    wait_for_completion: bool = True
    output_only: bool = False

class TaskResult(BaseModel):
    task_id: str
    status: Literal[ "pending", "processing", "completed", "failed" ]
    output: Optional[Any] = None
    error: Optional[Any] = None

    @classmethod
    def from_instance(cls, instance: TaskState) -> Self:
        return cls(
            task_id=instance.task_id,
            status=instance.status,
            output=instance.output,
            error=instance.error
        )

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

class WorkflowSchemaResult(BaseModel):
    workflow_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    input: List[WorkflowVariableResult]
    output: List[Union[WorkflowVariableResult, WorkflowVariableGroupResult]]

    @classmethod
    def from_instance(cls, instance: WorkflowSchema) -> Self:
        return cls(
            workflow_id=instance.workflow_id,
            title=instance.title,
            description=instance.description,
            input=[ cls._to_variable_result(variable) for variable in instance.input ],
            output=[ cls._to_variable_result(variable) for variable in instance.output ],
        )
    
    @classmethod
    def _to_variable_result(cls, variable: Union[WorkflowVariableConfig, WorkflowVariableGroupConfig ]) -> Union[WorkflowVariableResult, WorkflowVariableGroupResult]:
        if isinstance(variable, WorkflowVariableGroupConfig):
            return WorkflowVariableGroupResult.from_instance(variable)
        return WorkflowVariableResult.from_instance(variable)

@register_controller(ControllerType.HTTP_SERVER)
class HttpServerController(ControllerService):
    def __init__(
        self,
        config: HttpServerControllerConfig,
        components: List[ComponentConfig],
        listeners: List[ListenerConfig],
        gateways: List[GatewayConfig],
        workflows: List[WorkflowConfig],
        loggers: List[LoggerConfig],
        daemon: bool
    ):
        super().__init__(config, components, listeners, gateways, workflows, loggers, daemon)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.router: APIRouter = APIRouter()
        
        self._configure_server()
        self._configure_routes()
        self.app.include_router(self.router, prefix=self.config.base_path)

    def _configure_server(self) -> None:
        self.app.add_middleware(
            CORSMiddleware, 
            allow_origins=[self.config.origins], 
            allow_credentials=True, 
            allow_methods=["*"], 
            allow_headers=["*"],
        )

    def _configure_routes(self) -> None:
        @self.router.post("/workflows")
        async def run_workflow(
            request: Request
        ):
            body = await self._parse_workflow_body(request)
            state = await self.run_workflow(body.workflow_id, body.input, body.wait_for_completion)

            if body.output_only and not body.wait_for_completion:
                raise HTTPException(status_code=400, detail="output_only requires wait_for_completion=true.")
            
            if not body.output_only and isinstance(state.output, (StreamResource, AsyncGeneratorType)):
                raise HTTPException(status_code=400, detail="Streaming output is only allowed when output_only=true.")

            if body.output_only:
                return self._render_task_output(state)
            
            return self._render_task_state(state)

        @self.router.get("/tasks/{task_id}")
        async def get_task_state(
            task_id: str,
            output_only: bool = False
        ):
            state = self.get_task_state(task_id)

            if not state:
                raise HTTPException(status_code=404, detail="Task not found.")
            
            if not output_only and isinstance(state.output, (StreamResource, AsyncGeneratorType)):
                raise HTTPException(status_code=400, detail="Streaming output is only allowed when output_only=true.")

            if output_only:
                return self._render_task_output(state)

            return self._render_task_state(state)

        @self.router.get("/tasks/{task_id}/jobs")
        async def get_task_jobs(
            task_id: str
        ):
            return None

        @self.router.get("/workflows")
        async def get_workflow_schemas():
            return self._render_workflow_schemas(self.workflow_schemas)

        @self.router.get("/workflows/{workflow_id}")
        async def get_workflow_schema(
            workflow_id: str,
        ):
            workflow = self.workflow_schemas[workflow_id] if workflow_id in self.workflow_schemas else None

            if not workflow:
                raise HTTPException(status_code=404, detail="Workflow not found.")

            return self._render_workflow_schema(workflow)

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

    async def _parse_workflow_body(self, request: Request) -> WorkflowTaskRequestBody:
        content_type, _ = parse_options_header(request.headers, "Content-Type")

        if content_type not in [ "application/json", "multipart/form-data", "application/x-www-form-urlencoded" ]:
            if not content_type:
                raise HTTPException(status_code=400, detail="Missing or empty Content-Type header.")
            else:
                raise HTTPException(status_code=400, detail=f"Unsupported Content-Type: {content_type}")

        try:
            return WorkflowTaskRequestBody(**await parse_request_body(request, content_type, nested=True))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request body: {e}")

    def _render_task_state(self, state: TaskState) -> Response:
        return JSONResponse(content=TaskResult.from_instance(state).model_dump(exclude_none=True))

    def _render_task_output(self, state: TaskState) -> Response:
        if state.status in [ TaskStatus.PENDING, TaskStatus.PROCESSING ]:
            raise HTTPException(status_code=202, detail="Task is still in progress.")

        if state.status == TaskStatus.FAILED:
            raise HTTPException(status_code=500, detail=str(state.error))

        if isinstance(state.output, (HttpEventStreamResource, AsyncIterator)):
            return self._render_async_iterator(state.output)

        if isinstance(state.output, StreamResource):
            return self._render_stream_resource(state.output)

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

    def _render_workflow_schemas(self, workflows: Dict[str, WorkflowSchema]) -> Response:
        return JSONResponse(content={
            workflow_id: WorkflowSchemaResult.from_instance(workflow).model_dump(exclude_none=True) for workflow_id, workflow in workflows.items()
        })

    def _render_workflow_schema(self, workflow: WorkflowSchema) -> Response:
        return JSONResponse(content=WorkflowSchemaResult.from_instance(workflow).model_dump(exclude_none=True))
