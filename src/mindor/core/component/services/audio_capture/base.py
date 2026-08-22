from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioCaptureComponentConfig, AudioCaptureDriver
from mindor.dsl.schema.action import AudioCaptureActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class AudioCaptureService(AsyncService):
    def __init__(self, id: str, config: AudioCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioCaptureComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_capture_service(driver: AudioCaptureDriver):
    def decorator(cls: Type[AudioCaptureService]) -> Type[AudioCaptureService]:
        AudioCaptureServiceRegistry[driver] = cls
        return cls
    return decorator

AudioCaptureServiceRegistry: Dict[AudioCaptureDriver, Type[AudioCaptureService]] = {}
