from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoMixerComponentConfig, VideoMixerDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoMixerService, VideoMixerServiceRegistry
import importlib

@register_component(ComponentType.VIDEO_MIXER)
class VideoMixerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoMixerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VideoMixerService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoMixerDriver) -> VideoMixerService:
        try:
            if driver not in VideoMixerServiceRegistry:
                self._load_driver_module(driver)
            return VideoMixerServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video mixer driver: {driver}")

    def _load_driver_module(self, driver: VideoMixerDriver) -> None:
        """Import the module that registers the given video mixer driver.

        Convention: a driver "foo-bar" (VideoMixerDriver.value) maps to
        mindor.core.component.services.video_mixer.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_video_mixer_service
        decorator, populating VideoMixerServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_mixer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video mixer driver: {driver}") from e

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
