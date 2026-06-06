from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Callable, Any
from abc import ABC, abstractmethod
from mindor.dsl.schema.component import FileStoreComponentConfig, FileStoreDriver
from mindor.dsl.schema.action import FileStoreActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class FileStoreService(AsyncService):
    def __init__(self, id: str, config: FileStoreComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: FileStoreComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: FileStoreActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_file_store_service(driver: FileStoreDriver):
    def decorator(cls: Type[FileStoreService]) -> Type[FileStoreService]:
        FileStoreServiceRegistry[driver] = cls
        return cls
    return decorator

FileStoreServiceRegistry: Dict[FileStoreDriver, Type[FileStoreService]] = {}
