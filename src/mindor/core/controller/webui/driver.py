from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Dict, List, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller.webui import ControllerWebUIConfig
from mindor.dsl.schema.workflow import WorkflowConfig
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.workflow.schema import WorkflowSchema

if TYPE_CHECKING:
    from mindor.core.controller.runner import ControllerRunner

class WebUIDriver(ABC):
    requires_runner: bool = True

    def __init__(
        self,
        config: ControllerWebUIConfig,
        workflow_schemas: Dict[str, WorkflowSchema],
        workflows: List[WorkflowConfig],
        components: List[ComponentConfig]
    ):
        self.config = config
        self.workflow_schemas = workflow_schemas
        self.workflows = workflows
        self.components = components
        self.runner: Optional[ControllerRunner] = None

    async def start(self) -> None:
        from mindor.core.controller.runner import ControllerRunner

        if self.requires_runner:
            self.runner = ControllerRunner()

        try:
            await self._start()
        finally:
            if self.runner:
                await self.runner.close()
                self.runner = None

    async def stop(self) -> None:
        await self._stop()

    @abstractmethod
    async def _start(self) -> None:
        pass

    @abstractmethod
    async def _stop(self) -> None:
        pass
