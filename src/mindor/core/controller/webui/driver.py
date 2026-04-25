from __future__ import annotations

from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller.webui import ControllerWebUIConfig
from mindor.dsl.schema.controller import ControllerConfig, ControllerAdapterType
from mindor.core.controller.runner import ControllerRunner
from mindor.core.workflow.schema import WorkflowSchema

class WebUIDriver(ABC):
    requires_runner: bool = True

    def __init__(
        self,
        config: ControllerWebUIConfig,
        workflow_schemas: Dict[str, WorkflowSchema],
        controller_config: ControllerConfig
    ):
        self.config = config
        self.workflow_schemas = workflow_schemas
        self.controller_config = controller_config
        self.runner: Optional[ControllerRunner] = None

    async def start(self) -> None:
        if self.requires_runner:
            self.runner = ControllerRunner(self.controller_config)
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

    def _resolve_controller_url(self) -> str:
        for adapter in self.controller_config.adapters:
            if adapter.type == ControllerAdapterType.HTTP_SERVER:
                return f"http://localhost:{adapter.port}" + (adapter.base_path or "")
            if adapter.type == ControllerAdapterType.MCP_SERVER:
                return f"http://localhost:{adapter.port}" + (adapter.base_path or "")
        raise ValueError("No suitable adapter found for WebUI")
