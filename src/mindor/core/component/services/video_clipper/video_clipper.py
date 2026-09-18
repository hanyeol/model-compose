from typing import Any
from mindor.dsl.schema.component import VideoClipperComponentConfig, VideoClipperDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoClipperDriver, VideoClipperDriverRegistry
import importlib

@register_component(ComponentType.VIDEO_CLIPPER)
class VideoClipperComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoClipperComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: VideoClipperDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VideoClipperDriverType) -> VideoClipperDriver:
        try:
            if driver not in VideoClipperDriverRegistry:
                self._load_driver_module(driver)
            return VideoClipperDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video clipper driver: {driver}")

    def _load_driver_module(self, driver: VideoClipperDriverType) -> None:
        """Import the module that registers the given video clipper driver.

        Convention: a driver "foo-bar" (VideoClipperDriverType.value) maps to
        mindor.core.component.services.video_clipper.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_video_clipper_driver
        decorator, populating VideoClipperDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_clipper.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video clipper driver: {driver}") from e

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
