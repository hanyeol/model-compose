from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.job import JobConfig, JobType
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.workflow.context import WorkflowContext

class Job(ABC):
    def __init__(self, id: str, config: JobConfig, components: Dict[str, ComponentConfig]):
        self.id: str = id
        self.config: JobConfig = config
        self.components: Dict[str, ComponentConfig] = components

    @abstractmethod
    async def run(self, context: WorkflowContext) -> Any:
        pass

JobMap: Dict[JobType, Type[Job]] = {}
