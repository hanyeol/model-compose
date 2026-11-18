from typing import Any
from mindor.dsl.schema.component import VideoGradualSceneDetectorComponentConfig, VideoGradualSceneDetectorDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoGradualSceneDetectorDriver, VideoGradualSceneDetectorDriverRegistry
import importlib

@register_component(ComponentType.VIDEO_GRADUAL_SCENE_DETECTOR)
class VideoGradualSceneDetectorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoGradualSceneDetectorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: VideoGradualSceneDetectorDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VideoGradualSceneDetectorDriverType) -> VideoGradualSceneDetectorDriver:
        try:
            if driver not in VideoGradualSceneDetectorDriverRegistry:
                self._load_driver_module(driver)
            return VideoGradualSceneDetectorDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video gradual scene detector driver: {driver}")

    def _load_driver_module(self, driver: VideoGradualSceneDetectorDriverType) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_gradual_scene_detector.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video gradual scene detector driver: {driver}") from e

    async def _setup(self) -> None:
        await self.driver.setup()

    async def _teardown(self) -> None:
        await self.driver.teardown()

    async def _start(self) -> None:
        await self.driver.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.driver.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.driver.run(action, context)
