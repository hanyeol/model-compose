from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import VideoCaptureComponentConfig, VideoCaptureDriver
from mindor.dsl.schema.action import VideoCaptureActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class VideoCaptureService(AsyncService):
    def __init__(self, id: str, config: VideoCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: VideoCaptureComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: VideoCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: VideoCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_video_capture_service(driver: VideoCaptureDriver):
    def decorator(cls: Type[VideoCaptureService]) -> Type[VideoCaptureService]:
        VideoCaptureServiceRegistry[driver] = cls
        return cls
    return decorator

VideoCaptureServiceRegistry: Dict[VideoCaptureDriver, Type[VideoCaptureService]] = {}
