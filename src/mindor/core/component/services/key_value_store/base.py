from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import KeyValueStoreComponentConfig, KeyValueStoreDriver
from mindor.dsl.schema.action import KeyValueStoreActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class KeyValueStoreService(AsyncService):
    def __init__(self, id: str, config: KeyValueStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: KeyValueStoreComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_kv_store_service(driver: KeyValueStoreDriver):
    def decorator(cls: Type[KeyValueStoreService]) -> Type[KeyValueStoreService]:
        KeyValueStoreServiceRegistry[driver] = cls
        return cls
    return decorator

KeyValueStoreServiceRegistry: Dict[KeyValueStoreDriver, Type[KeyValueStoreService]] = {}
