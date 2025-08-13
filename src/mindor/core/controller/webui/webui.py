from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.controller.webui import ControllerWebUIConfig, ControllerWebUIDriver
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.controller.runner import ControllerRunner
from mindor.core.workflow.schema import WorkflowSchema, create_workflow_schemas
from mindor.core.services import AsyncService
from .gradio import GradioWebUIBuilder
from gradio import mount_gradio_app
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import uvicorn

class ControllerWebUI(AsyncService):
    def __init__(
        self,
        config: ControllerWebUIConfig,
        controller: ControllerConfig,
        components: List[ComponentConfig],
        workflows: List[WorkflowConfig],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerWebUIConfig = config
        self.controller: ControllerConfig = controller
        self.workflow_schemas: Dict[str, WorkflowSchema] = create_workflow_schemas(workflows, components)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.runner: ControllerRunner = None

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == ControllerWebUIDriver.GRADIO:
            blocks = GradioWebUIBuilder().build(
                workflow_schemas=self.workflow_schemas,
                workflow_runner=self._run_workflow
            )
            self.app = mount_gradio_app(self.app, blocks, path="")
            return

        if self.config.driver == ControllerWebUIDriver.STATIC:
            static_files = StaticFiles(
                directory=Path(self.config.static_dir).resolve(), 
                html=True
            )
            self.app.mount("/", static_files, name="static")
            return

    async def _serve(self) -> None:
        self.runner = ControllerRunner(self.controller)
        self.server = uvicorn.Server(uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        try:
            await self.server.serve()
        finally:
            await self.runner.close()
            self.server = None
            self.runner = None
    
    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True

    async def _run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        if self.runner:
            return await self.runner.run_workflow(workflow_id, input, self.workflow_schemas[workflow_id])
        return None
