from typing import Optional, List, Any
from mindor.dsl.schema.component import VideoPlaybackComponentConfig, VideoPlaybackDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoPlaybackService, VideoPlaybackServiceRegistry
import importlib

@register_component(ComponentType.VIDEO_PLAYBACK)
class VideoPlaybackComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoPlaybackComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VideoPlaybackService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoPlaybackDriver) -> VideoPlaybackService:
        try:
            if driver not in VideoPlaybackServiceRegistry:
                self._load_driver_module(driver)
            return VideoPlaybackServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video playback driver: {driver}")

    def _load_driver_module(self, driver: VideoPlaybackDriver) -> None:
        """Import the module that registers the given video playback driver.

        Convention: a driver "foo-bar" (VideoPlaybackDriver.value) maps to
        mindor.core.component.services.video_playback.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_video_playback_service
        decorator, populating VideoPlaybackServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_playback.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video playback driver: {driver}") from e

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
