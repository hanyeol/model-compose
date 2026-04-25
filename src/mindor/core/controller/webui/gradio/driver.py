from __future__ import annotations

from typing import Optional, Dict, Any
from ..driver import WebUIDriver
from .builder import GradioWebUIBuilder
from gradio import mount_gradio_app
from fastapi import FastAPI
import uvicorn

class GradioDriver(WebUIDriver):
    def __init__(self, config, workflow_schemas, controller_config):
        super().__init__(config, workflow_schemas, controller_config)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

        blocks = GradioWebUIBuilder().build(
            workflow_schemas=self.workflow_schemas,
            runner=lambda: self.runner
        )
        self.app = mount_gradio_app(self.app, blocks, path="")

    async def _start(self) -> None:
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

    async def _stop(self) -> None:
        if self.server:
            self.server.should_exit = True
