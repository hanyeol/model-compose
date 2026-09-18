from typing import Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoSceneDetectorComponentConfig, VideoSceneDetectorDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoSceneDetectorDriver, VideoSceneDetectorDriverRegistry
import importlib

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

        self.driver: VideoSceneDetectorDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VideoSceneDetectorDriverType) -> VideoSceneDetectorDriver:
        try:
            if driver not in VideoSceneDetectorDriverRegistry:
                self._load_driver_module(driver)
            return VideoSceneDetectorDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video scene detector driver: {driver}")

    def _load_driver_module(self, driver: VideoSceneDetectorDriverType) -> None:
        """Import the module that registers the given video scene detector driver.

        Convention: a driver "foo-bar" (VideoSceneDetectorDriverType.value) maps to
        mindor.core.component.services.video_scene_detector.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_video_scene_detector_driver
        decorator, populating VideoSceneDetectorDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_scene_detector.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video scene detector driver: {driver}") from e

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
