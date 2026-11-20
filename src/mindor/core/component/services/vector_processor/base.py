from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VectorProcessorComponentConfig, VectorProcessorDriverType
from mindor.dsl.schema.action import VectorProcessorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VectorProcessorDriver(ComponentDriver):
    config: VectorProcessorComponentConfig

    async def run(self, action: VectorProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VectorProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_vector_processor_driver(driver: VectorProcessorDriverType):
    def decorator(cls: Type[VectorProcessorDriver]) -> Type[VectorProcessorDriver]:
        VectorProcessorDriverRegistry[driver] = cls
        return cls
    return decorator

VectorProcessorDriverRegistry: Dict[VectorProcessorDriverType, Type[VectorProcessorDriver]] = {}
