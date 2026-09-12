from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import DocumentLoaderComponentConfig, DocumentLoaderDriver
from mindor.dsl.schema.action import DocumentLoaderActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class DocumentLoaderService(AsyncService):
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

def register_document_loader_service(driver: DocumentLoaderDriver):
    def decorator(cls: Type[DocumentLoaderService]) -> Type[DocumentLoaderService]:
        DocumentLoaderServiceRegistry[driver] = cls
        return cls
    return decorator

DocumentLoaderServiceRegistry: Dict[DocumentLoaderDriver, Type[DocumentLoaderService]] = {}
