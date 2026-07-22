from __future__ import annotations

from typing import Optional, Dict, Any
from ..driver import WebUIDriver
from .builder import GradioWebUIBuilder
from gradio import mount_gradio_app
from fastapi import FastAPI
import uvicorn

class GradioDriver(WebUIDriver):
    def __init__(self, config, workflow_schemas, workflows, components):
        super().__init__(config, workflow_schemas, workflows, components)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

        blocks, css = GradioWebUIBuilder().build(
            workflow_schemas=self.workflow_schemas,
            workflows=self.workflows,
            components=self.components,
            runner=lambda: self.runner
        )
        self.app = mount_gradio_app(self.app, blocks, path="", css=css)

    async def _start(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        self._configure_shutdown_handler(self.server)

        try:
            await self.server.serve()
        finally:
            self.server = None

    async def _stop(self) -> None:
        if self.server:
            self.server.should_exit = True

    def _configure_shutdown_handler(self, server: uvicorn.Server) -> None:
        shutdown = server.shutdown

        async def _shutdown(sockets=None) -> None:
            for connection in list(server.server_state.connections):
                connection.transport.close()
            await shutdown(sockets)

        server.shutdown = _shutdown
