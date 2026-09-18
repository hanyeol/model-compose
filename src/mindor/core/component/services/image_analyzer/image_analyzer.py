from typing import Any
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ImageAnalyzerDriver, ImageAnalyzerDriverRegistry
import importlib

@register_component(ComponentType.IMAGE_ANALYZER)
class ImageAnalyzerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ImageAnalyzerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: ImageAnalyzerDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: ImageAnalyzerDriverType) -> ImageAnalyzerDriver:
        try:
            if driver not in ImageAnalyzerDriverRegistry:
                self._load_driver_module(driver)
            return ImageAnalyzerDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported image analyzer driver: {driver}")

    def _load_driver_module(self, driver: ImageAnalyzerDriverType) -> None:
        """Import the module that registers the given image analyzer driver.

        Convention: a driver "foo-bar" (ImageAnalyzerDriverType.value) maps to
        mindor.core.component.services.image_analyzer.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_image_analyzer_driver
        decorator, populating ImageAnalyzerDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.image_analyzer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported image analyzer driver: {driver}") from e

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
