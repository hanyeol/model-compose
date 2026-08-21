from typing import Optional, List, Any
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ImageAnalyzerService, ImageAnalyzerServiceRegistry
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

        self.service: ImageAnalyzerService = self._create_service(self.config.driver)

    def _create_service(self, driver: ImageAnalyzerDriver) -> ImageAnalyzerService:
        try:
            if driver not in ImageAnalyzerServiceRegistry:
                self._load_driver_module(driver)
            return ImageAnalyzerServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported image analyzer driver: {driver}")

    def _load_driver_module(self, driver: ImageAnalyzerDriver) -> None:
        """Import the module that registers the given image analyzer driver.

        Convention: a driver "foo-bar" (ImageAnalyzerDriver.value) maps to
        mindor.core.component.services.image_analyzer.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_image_analyzer_service
        decorator, populating ImageAnalyzerServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.image_analyzer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported image analyzer driver: {driver}") from e

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
