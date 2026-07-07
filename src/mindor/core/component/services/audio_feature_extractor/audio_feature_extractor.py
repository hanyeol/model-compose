from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioFeatureExtractorComponentConfig, AudioFeatureExtractorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioFeatureExtractorService, AudioFeatureExtractorServiceRegistry

@register_component(ComponentType.AUDIO_FEATURE_EXTRACTOR)
class AudioFeatureExtractorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioFeatureExtractorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: AudioFeatureExtractorService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioFeatureExtractorDriver) -> AudioFeatureExtractorService:
        try:
            if not AudioFeatureExtractorServiceRegistry:
                from . import drivers
            return AudioFeatureExtractorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio feature extractor driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _start(self) -> None:
        await self.service.start()
        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
