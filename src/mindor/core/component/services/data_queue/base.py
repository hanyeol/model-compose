from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import DataQueueComponentConfig, DataQueueDriverType
from mindor.dsl.schema.action import DataQueueActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class DataQueueDriver(ComponentDriver):
    def __init__(self, id: str, config: DataQueueComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: DataQueueComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: DataQueueActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: DataQueueActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_data_queue_driver(driver: DataQueueDriverType):
    def decorator(cls: Type[DataQueueDriver]) -> Type[DataQueueDriver]:
        DataQueueDriverRegistry[driver] = cls
        return cls
    return decorator

DataQueueDriverRegistry: Dict[DataQueueDriverType, Type[DataQueueDriver]] = {}
