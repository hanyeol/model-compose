from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import DocumentLoaderComponentConfig, DocumentLoaderDriverType
from mindor.dsl.schema.action import DocumentLoaderActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class DocumentLoaderDriver(ComponentDriver):
    config: DocumentLoaderComponentConfig

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
