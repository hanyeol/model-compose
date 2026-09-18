from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriverType
from mindor.dsl.schema.action import AudioFeatureExtractorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class AudioFeatureExtractorDriver(ComponentDriver):
    def __init__(self, id: str, config: AudioFeatureExtractorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: AudioFeatureExtractorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: AudioFeatureExtractorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: AudioFeatureExtractorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_audio_feature_extractor_driver(driver: AudioFeatureExtractorDriverType):
    def decorator(cls: Type[AudioFeatureExtractorDriver]) -> Type[AudioFeatureExtractorDriver]:
        AudioFeatureExtractorDriverRegistry[driver] = cls
        return cls
    return decorator

AudioFeatureExtractorDriverRegistry: Dict[AudioFeatureExtractorDriverType, Type[AudioFeatureExtractorDriver]] = {}
