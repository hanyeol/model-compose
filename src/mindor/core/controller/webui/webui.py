from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerWebUIConfig, ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.controller.runner import ControllerRunner
from mindor.core.workflow.schema import create_workflow_schema
from mindor.core.services import AsyncService
from .gradio import GradioWebUIBuilder

from fastapi import FastAPI
from gradio import mount_gradio_app
import uvicorn, gradio

class ControllerWebUI(AsyncService):
    def __init__(
        self,
        config: ControllerWebUIConfig,
        controller: ControllerConfig,
        components: Dict[str, ComponentConfig],
        workflows: Dict[str, WorkflowConfig],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerWebUIConfig = config
        self.controller: ControllerConfig = controller
        self.components: Dict[str, ComponentConfig] = components
        self.workflows: Dict[str, WorkflowConfig] = workflows
        self.schema = create_workflow_schema(self.workflows, self.components)

        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.runner: ControllerRunner = None

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == "gradio":
            blocks: gradio.Blocks = GradioWebUIBuilder().build(
                schema=self.schema,
                runner=self._run_workflow
            )
            self.app = mount_gradio_app(self.app, blocks, path="")
            return

    async def _serve(self) -> None:
        self.runner = ControllerRunner(self.controller)
        self.server = uvicorn.Server(uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        await self.server.serve()
        await self.runner.close()
        self.server = None
        self.runner = None
    
    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True

    async def _run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        if self.runner:
            return await self.runner.run_workflow(workflow_id, input, self.schema[workflow_id])
        return None
