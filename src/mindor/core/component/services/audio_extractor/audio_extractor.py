from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioExtractorComponentConfig, AudioExtractorDriver
from mindor.dsl.schema.action import ActionConfig, AudioExtractorActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioExtractorService, AudioExtractorServiceRegistry

class AudioExtractorAction:
    def __init__(self, config: AudioExtractorActionConfig):
        self.config: AudioExtractorActionConfig = config

    async def run(self, context: ComponentActionContext, service: AudioExtractorService) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.AUDIO_EXTRACTOR)
class AudioExtractorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioExtractorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)
        self.service: AudioExtractorService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioExtractorDriver) -> AudioExtractorService:
        try:
            if not AudioExtractorServiceRegistry:
                from . import drivers
            return AudioExtractorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio extractor driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AudioExtractorAction(action).run(context, self.service)
