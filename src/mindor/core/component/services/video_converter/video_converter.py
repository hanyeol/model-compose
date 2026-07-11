from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoConverterComponentConfig, VideoConverterDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoConverterService, VideoConverterServiceRegistry
import importlib

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
            if driver not in VideoConverterServiceRegistry:
                _load_driver_module(driver)
            return VideoConverterServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video converter driver: {driver}")

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

def _load_driver_module(driver: VideoConverterDriver) -> None:
    """Import the module that registers the given video converter driver.

    Convention: a driver "foo-bar" (VideoConverterDriver.value) maps to
    mindor.core.component.services.video_converter.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_video_converter_service
    decorator, populating VideoConverterServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.video_converter.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported video converter driver: {driver}") from e
