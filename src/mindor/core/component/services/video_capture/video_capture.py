from typing import Any
from mindor.dsl.schema.component import VideoCaptureComponentConfig, VideoCaptureDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoCaptureDriver, VideoCaptureDriverRegistry
import importlib

@register_component(ComponentType.VIDEO_CAPTURE)
class VideoCaptureComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoCaptureComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: VideoCaptureDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VideoCaptureDriverType) -> VideoCaptureDriver:
        try:
            if driver not in VideoCaptureDriverRegistry:
                self._load_driver_module(driver)
            return VideoCaptureDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video capture driver: {driver}")

    def _load_driver_module(self, driver: VideoCaptureDriverType) -> None:
        """Import the module that registers the given video capture driver.

        Convention: a driver "foo-bar" (VideoCaptureDriverType.value) maps to
        mindor.core.component.services.video_capture.drivers.foo_bar.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_capture.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video capture driver: {driver}") from e

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
