from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoCaptureComponentConfig, VideoCaptureDriverType
from mindor.dsl.schema.action import VideoCaptureActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class VideoCaptureDriver(ComponentDriver):
    def __init__(self, id: str, config: VideoCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoCaptureComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_capture_driver(driver: VideoCaptureDriverType):
    def decorator(cls: Type[VideoCaptureDriver]) -> Type[VideoCaptureDriver]:
        VideoCaptureDriverRegistry[driver] = cls
        return cls
    return decorator

VideoCaptureDriverRegistry: Dict[VideoCaptureDriverType, Type[VideoCaptureDriver]] = {}
