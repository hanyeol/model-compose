from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.controller import ControllerWebUIConfig, ControllerConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.controller.runner import ControllerRunner
from mindor.core.services import AsyncService
from .schema import WorkflowSchema, WorkflowInputVariableResolver, WorkflowOutputVariableResolver
from .gradio import GradioWebUIBuilder

from fastapi import FastAPI, APIRouter, Body, HTTPException
import asyncio, uvicorn
from gradio import mount_gradio_app
import gradio

class ControllerWebUI(AsyncService):
    def __init__(
        self,
        config: ControllerWebUIConfig,
        controller: ControllerConfig,
        components: Dict[str, ComponentConfig],
        workflows: Dict[str, WorkflowConfig],
        env: Dict[str, str],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerWebUIConfig = config
        self.controller: ControllerConfig = controller
        self.components: Dict[str, ComponentConfig] = components
        self.workflows: Dict[str, WorkflowConfig] = workflows
        self.env: Dict[str, str] = env
        self.server: Optional[uvicorn.Server] = None
        self.app: FastAPI = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
        self.runner: ControllerRunner = ControllerRunner(controller)

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == "gradio":
            blocks: gradio.Blocks = GradioWebUIBuilder().build(
                schema=self._resolve_workflow_schema(),
                runner=self._run_workflow
            )
            self.app = mount_gradio_app(self.app, blocks, path="")
            return

    async def _serve(self) -> None:
        self.server = uvicorn.Server(uvicorn.Config(
            self.app,
            host=self.config.host,
            port=self.config.port,
            log_level="info"
        ))
        await self.server.serve()
    
    async def _shutdown(self) -> None:
        if self.server:
            self.server.should_exit = True
    
    async def _run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        return await self.runner.run_workflow(workflow_id, input)

    def _resolve_workflow_schema(self) -> Dict[str, WorkflowSchema]:
        schema: Dict[str, WorkflowSchema] = {}

        for workflow_id, workflow in self.workflows.items():
            schema[workflow_id] = WorkflowSchema(
                name=workflow.name,
                title=workflow.title, 
                description=workflow.description,
                input=WorkflowInputVariableResolver().resolve(workflow, self.components),
                output=WorkflowOutputVariableResolver().resolve(workflow, self.components)
            )

        return schema
