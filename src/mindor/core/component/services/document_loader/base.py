from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import DocumentLoaderComponentConfig, DocumentLoaderDriverType
from mindor.dsl.schema.action import DocumentLoaderActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class DocumentLoaderDriver(ComponentDriver):
    def __init__(self, id: str, config: DocumentLoaderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: DocumentLoaderComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: DocumentLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: DocumentLoaderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_document_loader_driver(driver: DocumentLoaderDriverType):
    def decorator(cls: Type[DocumentLoaderDriver]) -> Type[DocumentLoaderDriver]:
        DocumentLoaderDriverRegistry[driver] = cls
        return cls
    return decorator

DocumentLoaderDriverRegistry: Dict[DocumentLoaderDriverType, Type[DocumentLoaderDriver]] = {}
