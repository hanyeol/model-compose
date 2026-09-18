from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioCaptureComponentConfig, AudioCaptureDriverType
from mindor.dsl.schema.action import AudioCaptureActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioCaptureDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioCaptureComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioCaptureComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioCaptureActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioCaptureActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_capture_driver(driver: AudioCaptureDriverType):
    def decorator(cls: Type[AudioCaptureDriver]) -> Type[AudioCaptureDriver]:
        AudioCaptureDriverRegistry[driver] = cls
        return cls
    return decorator

AudioCaptureDriverRegistry: Dict[AudioCaptureDriverType, Type[AudioCaptureDriver]] = {}
