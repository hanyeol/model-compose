from typing import Any
from mindor.dsl.schema.component import ScreenCaptureComponentConfig, ScreenCaptureDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ScreenCaptureDriver, ScreenCaptureDriverRegistry
import importlib

@register_component(ComponentType.SCREEN_CAPTURE)
class ScreenCaptureComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ScreenCaptureComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: ScreenCaptureDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: ScreenCaptureDriverType) -> ScreenCaptureDriver:
        try:
            if driver not in ScreenCaptureDriverRegistry:
                self._load_driver_module(driver)
            return ScreenCaptureDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported screen capture driver: {driver}")

    def _load_driver_module(self, driver: ScreenCaptureDriverType) -> None:
        """Import the module that registers the given screen capture driver.

        Convention: a driver "foo-bar" (ScreenCaptureDriverType.value) maps to
        mindor.core.component.services.screen_capture.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_screen_capture_driver
        decorator, populating ScreenCaptureDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.screen_capture.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported screen capture driver: {driver}") from e

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
