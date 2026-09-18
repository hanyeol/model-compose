from typing import Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig, VideoFrameExtractorDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoFrameExtractorDriver, VideoFrameExtractorDriverRegistry
import importlib

@register_component(ComponentType.VIDEO_FRAME_EXTRACTOR)
class VideoFrameExtractorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoFrameExtractorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: VideoFrameExtractorDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VideoFrameExtractorDriverType) -> VideoFrameExtractorDriver:
        try:
            if driver not in VideoFrameExtractorDriverRegistry:
                self._load_driver_module(driver)
            return VideoFrameExtractorDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video frame extractor driver: {driver}")

    def _load_driver_module(self, driver: VideoFrameExtractorDriverType) -> None:
        """Import the module that registers the given video frame extractor driver.

        Convention: a driver "foo-bar" (VideoFrameExtractorDriverType.value) maps to
        mindor.core.component.services.video_frame_extractor.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_video_frame_extractor_driver
        decorator, populating VideoFrameExtractorDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_frame_extractor.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video frame extractor driver: {driver}") from e

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
