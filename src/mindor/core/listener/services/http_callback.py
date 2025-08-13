from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, AsyncIterator, Any

from mindor.dsl.schema.listener import HttpCallbackListenerConfig, HttpCallbackConfig
from mindor.core.utils.http_request import parse_request_body, parse_options_header
from mindor.core.utils.renderers import VariableRenderer
from ..base import ListenerService, ListenerType, register_listener

from fastapi import FastAPI, APIRouter, Body, HTTPException, Request
from fastapi.responses import Response, JSONResponse
from threading import Lock
import asyncio, uvicorn

_pending_futures: Dict[str, asyncio.Future] = {}
_pending_futures_lock: Lock = Lock()

class HttpCallbackContext:
    def __init__(self, body: Optional[Any], query: Optional[Dict[str, str]], bulk: bool, item: Optional[str]):
        self.body: Optional[Any] = body
        self.query: Optional[Dict[str, str]] = query
        self.bulk: bool = bulk
        self.item: Optional[str] = item
        self.renderer: VariableRenderer = VariableRenderer(self._resolve_source)

    async def items(self) -> AsyncIterator["HttpCallbackContext"]:
        for item in await self._items():
            yield HttpCallbackContext(item, self.query, False, None)

    async def render_variable(self, template: str, ignore_files: bool = True) -> Any:
        return await self.renderer.render(template, ignore_files)

    async def _items(self) -> List[Any]:
        item = await self.renderer.render(self.item) if self.item else self.body

        if self.bulk:
            if not isinstance(item, list):
               raise ValueError("Expected a list because 'bulk' is true, but got a non-list.")
            return item

        return [ item ]

    async def _resolve_source(self, key: str, index: Optional[int]) -> Any:
        if key == "body" or key == "item":
            return self.body

        if key == "query":
            return self.query

        raise KeyError(f"Unknown source: {key}")

@register_listener(ListenerType.HTTP_CALLBACK)
class HttpCallbackListener(ListenerService):
    def __init__(self, id: str, config: HttpCallbackListenerConfig, daemon: bool):
        super().__init__(id, config, daemon)
        
        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.router: APIRouter = APIRouter()

        self._configure_routes()
        self.app.include_router(self.router, prefix=self.config.base_path)

    def _configure_routes(self) -> None:
        for callback in self.config.callbacks:
            self.router.add_api_route(
                path=callback.path,
                endpoint=self._make_callback_handler(callback),
                methods=[callback.method],
                name=f"callback_{callback.path.strip('/').replace('/', '_')}",
            )

    def _make_callback_handler(self, callback: HttpCallbackConfig) -> Callable:
        async def _handler(request: Request) -> Response:
            content_type, _ = parse_options_header(request.headers, "Content-Type")
            body, query = await parse_request_body(request, content_type), request.query_params
            context = HttpCallbackContext(body, query, callback.bulk, callback.item)
            succeeded = await self._is_callback_succeeded(callback, context)

            async for item in context.items():
                callback_id = await item.render_variable(callback.identify_by) if callback.identify_by else "__default__"
                future: asyncio.Future = self._get_pending_future(callback_id)

                if future:
                    if succeeded:
                        future.set_result((await item.render_variable(callback.result, ignore_files=True)) if callback.result else item.body)
                    else:
                        future.set_exception(RuntimeError(f"Task failed for '{callback_id}'"))
                    self._remove_pending_future(callback_id)

            return Response()

        return _handler

    async def _is_callback_succeeded(self, callback: HttpCallbackConfig, context: HttpCallbackContext) -> bool:
        status = (await context.render_variable(callback.status)) if callback.status else None

        if status:
            if status in (callback.success_when or []):
                return True
            if status in (callback.fail_when or []):
                return False

        return True

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

    def _get_pending_future(self, id: str) -> Optional[asyncio.Future]:
        with _pending_futures_lock:
            return _pending_futures.get(id)

    def _remove_pending_future(self, id: str) -> None:
        with _pending_futures_lock:
            _pending_futures.pop(id, None)

    @classmethod
    def register_pending_future(cls, id: str, future: asyncio.Future) -> None:
        with _pending_futures_lock:
            _pending_futures[id] = future
