from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoFrameExtractorComponentConfig, VideoFrameExtractorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoFrameExtractorService, VideoFrameExtractorServiceRegistry
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

        self.service: VideoFrameExtractorService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoFrameExtractorDriver) -> VideoFrameExtractorService:
        try:
            if driver not in VideoFrameExtractorServiceRegistry:
                _load_driver_module(driver)
            return VideoFrameExtractorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video frame extractor driver: {driver}")

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

def _load_driver_module(driver: VideoFrameExtractorDriver) -> None:
    """Import the module that registers the given video frame extractor driver.

    Convention: a driver "foo-bar" (VideoFrameExtractorDriver.value) maps to
    mindor.core.component.services.video_frame_extractor.drivers.foo_bar —
    either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_video_frame_extractor_service
    decorator, populating VideoFrameExtractorServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.video_frame_extractor.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported video frame extractor driver: {driver}") from e
