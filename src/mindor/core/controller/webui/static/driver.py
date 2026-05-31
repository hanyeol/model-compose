from __future__ import annotations

from typing import Optional
from ..driver import WebUIDriver
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

class StaticDriver(WebUIDriver):
    requires_runner = False

    def __init__(self, config, workflow_schemas):
        super().__init__(config, workflow_schemas)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)

        static_files = StaticFiles(
            directory=Path(self.config.static_dir).resolve(),
            html=True
        )
        self.app.mount("/", static_files, name="static")

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
