from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import SubtitleLoaderComponentConfig, SubtitleLoaderDriverType
from mindor.dsl.schema.action import SubtitleLoaderActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class SubtitleLoaderDriver(ComponentDriver):
    def __init__(self, id: str, config: SubtitleLoaderComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: SubtitleLoaderComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

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
