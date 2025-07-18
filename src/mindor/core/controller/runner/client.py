from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.controller import ControllerConfig
from mindor.core.workflow.schema import WorkflowSchema

class ControllerClient(ABC):
    def __init__(self, config: ControllerConfig):
        self.config: ControllerConfig = config

    @abstractmethod
    async def run_workflow(self, workflow_id: Optional[str], input: Any) -> Any:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass
