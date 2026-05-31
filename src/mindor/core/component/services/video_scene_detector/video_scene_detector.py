from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig, VideoSceneDetectorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoSceneDetectorService, VideoSceneDetectorServiceRegistry

@register_component(ComponentType.VIDEO_SCENE_DETECTOR)
class VideoSceneDetectorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoSceneDetectorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VideoSceneDetectorService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoSceneDetectorDriver) -> VideoSceneDetectorService:
        try:
            if not VideoSceneDetectorServiceRegistry:
                from . import drivers
            return VideoSceneDetectorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video scene detector driver: {driver}")

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return self.service.get_setup_requirements()

    async def _serve(self) -> None:
        await self.service.start()

    async def _shutdown(self) -> None:
        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
