from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller import ControllerConfig, ControllerAdapterType
from mindor.core.workflow.schema import WorkflowSchema
from .client import ControllerClient
from .http_client import HttpControllerClient
from .mcp_client import McpControllerClient

class ControllerRunner:
    def __init__(self, config: ControllerConfig):
        self.config: ControllerConfig = config
        self.client: ControllerClient = None

        self._configure_client()

    def _configure_client(self) -> None:
        for adapter in self.config.adapters:
            if adapter.type == ControllerAdapterType.HTTP_SERVER:
                self.client = HttpControllerClient(adapter)
                return

            if adapter.type == ControllerAdapterType.MCP_SERVER:
                self.client = McpControllerClient(adapter)
                return

        raise ValueError("No suitable adapter found for controller runner")

    async def run_workflow(self, workflow_id: Optional[str], input: Any, schema: WorkflowSchema) -> Any:
        return await self.client.run_workflow(workflow_id, input, schema)

    async def resume_workflow(self, task_id: str, job_id: str, answer: Any = None) -> dict:
        return await self.client.resume_workflow(task_id, job_id, answer)

    async def wait_for_completion(self, task_id: str) -> dict:
        return await self.client.wait_for_completion(task_id)

    async def get_task_output(self, task_id: str) -> Any:
        return await self.client.get_task_output(task_id)

    async def close(self) -> None:
        await self.client.close()
