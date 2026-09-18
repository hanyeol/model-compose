from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import MediaInspectorComponentConfig, MediaInspectorDriverType
from mindor.dsl.schema.action import MediaInspectorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class MediaInspectorDriver(ComponentDriver):
    def __init__(self, id: str, config: MediaInspectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: MediaInspectorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: MediaInspectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_media_inspector_driver(driver: MediaInspectorDriverType):
    def decorator(cls: Type[MediaInspectorDriver]) -> Type[MediaInspectorDriver]:
        MediaInspectorDriverRegistry[driver] = cls
        return cls
    return decorator

MediaInspectorDriverRegistry: Dict[MediaInspectorDriverType, Type[MediaInspectorDriver]] = {}
