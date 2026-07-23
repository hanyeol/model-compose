from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import DataQueueComponentConfig, DataQueueDriver
from mindor.dsl.schema.action import DataQueueActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class DataQueueService(AsyncService):
    def __init__(self, id: str, config: DataQueueComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: DataQueueComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: DataQueueActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: DataQueueActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_data_queue_service(driver: DataQueueDriver):
    def decorator(cls: Type[DataQueueService]) -> Type[DataQueueService]:
        DataQueueServiceRegistry[driver] = cls
        return cls
    return decorator

DataQueueServiceRegistry: Dict[DataQueueDriver, Type[DataQueueService]] = {}
