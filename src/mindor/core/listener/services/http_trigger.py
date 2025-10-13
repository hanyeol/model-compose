from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, AsyncIterator, Self, Any
from pydantic import BaseModel
from mindor.dsl.schema.listener import HttpTriggerListenerConfig, HttpTriggerConfig
from mindor.core.controller import ControllerService, TaskState
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.renderers import VariableRenderer
from ..base import ListenerService, ListenerType, register_listener
from fastapi import FastAPI, APIRouter, Body, HTTPException, Request
from fastapi.responses import Response, JSONResponse
import asyncio, uvicorn

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

    @classmethod
    def to_dict(cls, instance: TaskState) -> Dict[str, Any]:
        return cls.from_instance(instance).model_dump(exclude_none=True)

class HttpTriggerContext:
    def __init__(self, body: Optional[Any], query: Optional[Dict[str, str]], bulk: bool, item: Optional[str]):
        self.body: Optional[Any] = body
        self.query: Optional[Dict[str, str]] = query
        self.bulk: bool = bulk
        self.item: Optional[str] = item
        self.renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    async def items(self) -> AsyncIterator["HttpTriggerContext"]:
        for item in await self._items():
            yield HttpTriggerContext(item, self.query, False, None)

    async def render_variable(self, template: str, ignore_files: bool = True) -> Any:
        return await self.renderer.render(template, ignore_files)

    async def _items(self) -> List[Any]:
        item = await self.renderer.render(self.item) if self.item else self.body

        if self.bulk:
            if not isinstance(item, list):
               raise ValueError("Expected a list because 'bulk' is true, but got a non-list")
            return item

        return [ item ]

    async def _resolve_source(self, key: str, index: Optional[int]) -> Any:
        if key == "body" or key == "item":
            return self.body

        if key == "query":
            return self.query

        raise KeyError(f"Unknown source: {key}")

@register_listener(ListenerType.HTTP_TRIGGER)
class HttpTriggerListener(ListenerService):
    def __init__(self, id: str, config: HttpTriggerListenerConfig, daemon: bool):
        super().__init__(id, config, daemon)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.router: APIRouter = APIRouter()

        self._configure_routes()
        self.app.include_router(self.router, prefix=self.config.base_path or "")

    def _configure_routes(self) -> None:
        for trigger in self.config.triggers:
            self.router.add_api_route(
                path=trigger.path,
                endpoint=self._make_trigger_handler(trigger),
                methods=[trigger.method],
                name=f"trigger_{trigger.path.strip('/').replace('/', '_')}",
            )

    def _make_trigger_handler(self, trigger: HttpTriggerConfig) -> Callable:
        async def _handler(request: Request) -> Response:
            controller = ControllerService.get_shared_instance()
            content_type, _ = parse_options_header(request.headers, "Content-Type")
            body, query = await parse_request_body(request, content_type), request.query_params
            context = HttpTriggerContext(body, query, trigger.bulk, trigger.item)
            states: List[TaskState] = []

            async for item in context.items():
                workflow_id = await item.render_variable(trigger.workflow)
                input       = await item.render_variable(trigger.input)

                try:
                    state = await controller.run_workflow(workflow_id, input, wait_for_completion=False)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to trigger workflow: {str(e)}")

                states.append(state)

            return self._render_task_states(states, trigger.bulk)

        return _handler

    def _render_task_states(self, states: List[TaskState], bulk: bool) -> Response:
        if bulk:
            return JSONResponse(content=[ TaskResult.to_dict(state) for state in states ])
        else:
            return JSONResponse(content=TaskResult.to_dict(states[0]))

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
