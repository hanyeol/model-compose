from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioSilenceDetectorComponentConfig, AudioSilenceDetectorDriverType
from mindor.dsl.schema.action import AudioSilenceDetectorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioSilenceDetectorDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioSilenceDetectorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioSilenceDetectorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioSilenceDetectorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioSilenceDetectorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_silence_detector_driver(driver: AudioSilenceDetectorDriverType):
    def decorator(cls: Type[AudioSilenceDetectorDriver]) -> Type[AudioSilenceDetectorDriver]:
        AudioSilenceDetectorDriverRegistry[driver] = cls
        return cls
    return decorator

AudioSilenceDetectorDriverRegistry: Dict[AudioSilenceDetectorDriverType, Type[AudioSilenceDetectorDriver]] = {}
