from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioConverterComponentConfig, AudioConverterDriver
from mindor.dsl.schema.action import ActionConfig, AudioConverterActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioConverterService, AudioConverterServiceRegistry

class AudioConverterAction:
    def __init__(self, config: AudioConverterActionConfig):
        self.config: AudioConverterActionConfig = config

    async def run(self, context: ComponentActionContext, service: AudioConverterService) -> Any:
        return await service.run(self.config, context)

@register_component(ComponentType.AUDIO_CONVERTER)
class AudioConverterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioConverterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)
        self.service: AudioConverterService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioConverterDriver) -> AudioConverterService:
        try:
            if not AudioConverterServiceRegistry:
                from . import drivers
            return AudioConverterServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio converter driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await AudioConverterAction(action).run(context, self.service)
