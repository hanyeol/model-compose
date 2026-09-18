from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ScreenCaptureComponentConfig, ScreenCaptureDriverType
from mindor.dsl.schema.action import ScreenCaptureActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ScreenCaptureDriver(ComponentDriver):
    def __init__(self, id: str, config: ScreenCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ScreenCaptureComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ScreenCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ScreenCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_screen_capture_driver(driver: ScreenCaptureDriverType):
    def decorator(cls: Type[ScreenCaptureDriver]) -> Type[ScreenCaptureDriver]:
        ScreenCaptureDriverRegistry[driver] = cls
        return cls
    return decorator

ScreenCaptureDriverRegistry: Dict[ScreenCaptureDriverType, Type[ScreenCaptureDriver]] = {}
