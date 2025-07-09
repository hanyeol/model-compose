from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller import ControllerConfig
from mindor.dsl.schema.workflow import WorkflowVariableConfig, WorkflowVariableGroupConfig
from mindor.core.workflow.schema import WorkflowSchema
from .client import ControllerClient
from .http_client import HttpControllerClient
from .mcp_client import McpControllerClient

class ControllerClient(ABC):
    def __init__(self, config: ControllerConfig):
        self.config: ControllerConfig = config

    @abstractmethod
    async def run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass

class ControllerRunner:
    def __init__(self, config: ControllerConfig):
        self.config: ControllerConfig = config
        self.client: ControllerClient = None

        self._configure_client()

    def _configure_client(self) -> None:
        if self.config.type == "http-server":
            self.client = HttpControllerClient(self.config)
            return

        if self.config.type == "mcp-server":
            self.client = McpControllerClient(self.config)
            return

        raise ValueError(f"Unsupported controller type: {self.config.type}")
    
    async def run_workflow(self, workflow_id: Optional[str], input: Any, schema: WorkflowSchema) -> Any:
        return await self.client.run_workflow(workflow_id, input, schema)

    async def close(self) -> None:
        await self.client.close()
