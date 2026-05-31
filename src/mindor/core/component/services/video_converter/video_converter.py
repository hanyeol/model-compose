from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoConverterComponentConfig, VideoConverterDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoConverterService, VideoConverterServiceRegistry

@register_component(ComponentType.VIDEO_CONVERTER)
class VideoConverterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoConverterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)
        self.service: VideoConverterService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoConverterDriver) -> VideoConverterService:
        try:
            if not VideoConverterServiceRegistry:
                from . import drivers
            return VideoConverterServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video converter driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
