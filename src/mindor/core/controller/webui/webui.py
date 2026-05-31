from __future__ import annotations

from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated
from mindor.dsl.schema.controller.webui import ControllerWebUIConfig, ControllerWebUIDriver
from mindor.dsl.schema.component import ComponentConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.core.workflow.schema import WorkflowSchema, create_workflow_schemas
from mindor.core.foundation import AsyncService
from .driver import WebUIDriver

WebUIInstance: Optional[ControllerWebUI] = None

class ControllerWebUI(AsyncService):
    def __init__(
        self,
        config: ControllerWebUIConfig,
        components: List[ComponentConfig],
        workflows: List[WorkflowConfig],
        daemon: bool
    ):
        super().__init__(daemon)

        self.config: ControllerWebUIConfig = config
        self.workflow_schemas: Dict[str, WorkflowSchema] = create_workflow_schemas(workflows, components, exclude_private=True)

        self.driver: Optional[WebUIDriver] = None

        self._configure_driver()

    def _configure_driver(self) -> None:
        if self.config.driver == ControllerWebUIDriver.GRADIO:
            from .gradio import GradioDriver
            self.driver = GradioDriver(self.config, self.workflow_schemas)
            return

        if self.config.driver == ControllerWebUIDriver.STATIC:
            from .static import StaticDriver
            self.driver = StaticDriver(self.config, self.workflow_schemas)
            return

    async def _serve(self) -> None:
        if self.driver:
            try:
                await self.driver.start()
            finally:
                await self.driver.stop()

    async def _shutdown(self) -> None:
        if self.driver:
            await self.driver.stop()

def create_webui(config: ControllerWebUIConfig, components: List[ComponentConfig], workflows: List[WorkflowConfig], daemon: bool) -> ControllerWebUI:
    global WebUIInstance

    if not WebUIInstance:
        WebUIInstance = ControllerWebUI(config, components, workflows, daemon)

    return WebUIInstance
