from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import SubtitleLoaderComponentConfig, SubtitleLoaderDriverType
from mindor.dsl.schema.action import SubtitleLoaderActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class SubtitleLoaderDriver(ComponentDriver):
    config: SubtitleLoaderComponentConfig

    async def run(self, action: SubtitleLoaderActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: SubtitleLoaderActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_subtitle_loader_driver(driver: SubtitleLoaderDriverType):
    def decorator(cls: Type[SubtitleLoaderDriver]) -> Type[SubtitleLoaderDriver]:
        SubtitleLoaderDriverRegistry[driver] = cls
        return cls
    return decorator

SubtitleLoaderDriverRegistry: Dict[SubtitleLoaderDriverType, Type[SubtitleLoaderDriver]] = {}
