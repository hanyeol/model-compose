from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ScreenCaptureComponentConfig, ScreenCaptureDriver
from mindor.dsl.schema.action import ScreenCaptureActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class ScreenCaptureService(AsyncService):
    def __init__(self, id: str, config: ScreenCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ScreenCaptureComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ScreenCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ScreenCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_screen_capture_service(driver: ScreenCaptureDriver):
    def decorator(cls: Type[ScreenCaptureService]) -> Type[ScreenCaptureService]:
        ScreenCaptureServiceRegistry[driver] = cls
        return cls
    return decorator

ScreenCaptureServiceRegistry: Dict[ScreenCaptureDriver, Type[ScreenCaptureService]] = {}
