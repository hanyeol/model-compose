from typing import Optional, List, Any
from mindor.dsl.schema.component import ImageDrawingComponentConfig, ImageDrawingDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ImageDrawingService, ImageDrawingServiceRegistry
import importlib

@register_component(ComponentType.IMAGE_DRAWING)
class ImageDrawingComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ImageDrawingComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: ImageDrawingService = self._create_service(self.config.driver)

    def _create_service(self, driver: ImageDrawingDriver) -> ImageDrawingService:
        try:
            if driver not in ImageDrawingServiceRegistry:
                self._load_driver_module(driver)
            return ImageDrawingServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported image drawing driver: {driver}")

    def _load_driver_module(self, driver: ImageDrawingDriver) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.image_drawing.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported image drawing driver: {driver}") from e

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
