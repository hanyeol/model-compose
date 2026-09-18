from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import KeyValueStoreComponentConfig, KeyValueStoreDriverType
from mindor.dsl.schema.action import KeyValueStoreActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class KeyValueStoreDriver(ComponentDriver):
    def __init__(self, id: str, config: KeyValueStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: KeyValueStoreComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: KeyValueStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_kv_store_service(driver: KeyValueStoreDriverType):
    def decorator(cls: Type[KeyValueStoreDriver]) -> Type[KeyValueStoreDriver]:
        KeyValueStoreDriverRegistry[driver] = cls
        return cls
    return decorator

KeyValueStoreDriverRegistry: Dict[KeyValueStoreDriverType, Type[KeyValueStoreDriver]] = {}
