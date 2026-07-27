from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VectorProcessorComponentConfig, VectorProcessorDriver
from mindor.dsl.schema.action import VectorProcessorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VectorProcessorService(AsyncService):
    def __init__(self, id: str, config: VectorProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VectorProcessorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VectorProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VectorProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_vector_processor_service(driver: VectorProcessorDriver):
    def decorator(cls: Type[VectorProcessorService]) -> Type[VectorProcessorService]:
        VectorProcessorServiceRegistry[driver] = cls
        return cls
    return decorator

VectorProcessorServiceRegistry: Dict[VectorProcessorDriver, Type[VectorProcessorService]] = {}
