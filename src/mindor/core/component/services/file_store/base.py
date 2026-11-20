from typing import Type, Literal, Optional, Dict, List, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import FileStoreComponentConfig, FileStoreDriverType
from mindor.dsl.schema.action import FileStoreActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class FileStoreDriver(ComponentDriver):
    config: FileStoreComponentConfig

    async def run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_file_store_driver(driver: FileStoreDriverType):
    def decorator(cls: Type[FileStoreDriver]) -> Type[FileStoreDriver]:
        FileStoreDriverRegistry[driver] = cls
        return cls
    return decorator

FileStoreDriverRegistry: Dict[FileStoreDriverType, Type[FileStoreDriver]] = {}
