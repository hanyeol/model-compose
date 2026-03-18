from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller import ControllerAdapterConfig
from mindor.core.workflow.schema import WorkflowSchema

class ControllerClient(ABC):
    def __init__(self, config: ControllerAdapterConfig):
        self.config: ControllerAdapterConfig = config

    @abstractmethod
    async def run_workflow(self, workflow_id: Optional[str], input: Any, workflow: WorkflowSchema) -> Any:
        pass

    @abstractmethod
    async def resume_workflow(self, task_id: str, job_id: str, answer: Any = None) -> dict:
        pass

    @abstractmethod
    async def wait_for_completion(self, task_id: str) -> dict:
        pass

    @abstractmethod
    async def get_task_output(self, task_id: str) -> Any:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
