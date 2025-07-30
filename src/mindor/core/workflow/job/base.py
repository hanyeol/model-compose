from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.job import JobConfig, JobType
from mindor.dsl.schema.component import ComponentConfig
from mindor.core.component import ComponentGlobalConfigs
from mindor.core.workflow.context import WorkflowContext

class RoutingTarget:
    def __init__(self, job_id):
        self.job_id = job_id

class Job(ABC):
    def __init__(self, id: str, config: JobConfig, global_configs: ComponentGlobalConfigs):
        self.id: str = id
        self.config: JobConfig = config
        self.global_configs: ComponentGlobalConfigs = global_configs

    @abstractmethod
    async def run(self, context: WorkflowContext) -> Union[Any, RoutingTarget]:
        pass

def register_job(type: JobType):
    def decorator(cls: Type[Job]) -> Type[Job]:
        JobRegistry[type] = cls
        return cls
    return decorator

JobRegistry: Dict[JobType, Type[Job]] = {}
