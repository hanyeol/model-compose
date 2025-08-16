from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import VectorStoreComponentConfig, VectorStoreDriver
from mindor.dsl.schema.action import VectorStoreActionConfig
from mindor.core.services import AsyncService
from ...context import ComponentActionContext

class VectorStoreService(AsyncService):
    def __init__(self, id: str, config: VectorStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VectorStoreComponentConfig = config

    async def run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VectorStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_vector_store_service(driver: VectorStoreDriver):
    def decorator(cls: Type[VectorStoreService]) -> Type[VectorStoreService]:
        VectorStoreServiceRegistry[driver] = cls
        return cls
    return decorator

VectorStoreServiceRegistry: Dict[VectorStoreDriver, Type[VectorStoreService]] = {}
