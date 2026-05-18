from typing import Type, Optional, Dict, Any
from abc import abstractmethod
from mindor.dsl.schema.tracer import TracerConfig
from mindor.dsl.schema.tracer.impl.types import TracerDriver
from mindor.core.foundation import AsyncService

class TracerService(AsyncService):
    def __init__(self, id: str, config: TracerConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: TracerConfig = config

    @abstractmethod
    def on_workflow_start(self, task_id: str, workflow_id: str, input: Any, session_id: Optional[str], metadata: Any) -> None:
        pass

    @abstractmethod
    def on_workflow_end(self, task_id: str, workflow_id: str, output: Any, elapsed: float) -> None:
        pass

    @abstractmethod
    def on_workflow_error(self, task_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        pass

    @abstractmethod
    def on_job_start(self, task_id: str, job_id: str, workflow_id: str, input: Any) -> None:
        pass

    @abstractmethod
    def on_job_end(self, task_id: str, job_id: str, workflow_id: str, output: Any, elapsed: float) -> None:
        pass

    @abstractmethod
    def on_job_error(self, task_id: str, job_id: str, workflow_id: str, error: Exception, elapsed: float) -> None:
        pass

def register_tracer(driver: TracerDriver):
    def decorator(cls: Type[TracerService]) -> Type[TracerService]:
        TracerRegistry[driver] = cls
        return cls
    return decorator

TracerRegistry: Dict[TracerDriver, Type[TracerService]] = {}
