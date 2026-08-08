from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MediaInspectorComponentConfig, MediaInspectorDriver
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class MediaInspectorService(AsyncService):
    def __init__(self, id: str, config: MediaInspectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MediaInspectorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_media_inspector_service(driver: MediaInspectorDriver):
    def decorator(cls: Type[MediaInspectorService]) -> Type[MediaInspectorService]:
        MediaInspectorServiceRegistry[driver] = cls
        return cls
    return decorator

MediaInspectorServiceRegistry: Dict[MediaInspectorDriver, Type[MediaInspectorService]] = {}
