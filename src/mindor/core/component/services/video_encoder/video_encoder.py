from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VideoEncoderComponentConfig, VideoEncoderDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoEncoderService, VideoEncoderServiceRegistry
import importlib

@register_component(ComponentType.VIDEO_ENCODER)
class VideoEncoderComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoEncoderComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VideoEncoderService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoEncoderDriver) -> VideoEncoderService:
        try:
            if driver not in VideoEncoderServiceRegistry:
                _load_driver_module(driver)
            return VideoEncoderServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video encoder driver: {driver}")

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

def _load_driver_module(driver: VideoEncoderDriver) -> None:
    """Import the module that registers the given video encoder driver.

    Convention: a driver "foo-bar" (VideoEncoderDriver.value) maps to
    mindor.core.component.services.video_encoder.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_video_encoder_service
    decorator, populating VideoEncoderServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.video_encoder.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported video encoder driver: {driver}") from e
