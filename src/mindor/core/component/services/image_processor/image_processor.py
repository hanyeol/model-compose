from typing import Optional, List, Any
from mindor.dsl.schema.component import ImageProcessorComponentConfig, ImageProcessorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ImageProcessorService, ImageProcessorServiceRegistry
import importlib

@register_component(ComponentType.IMAGE_PROCESSOR)
class ImageProcessorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ImageProcessorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: ImageProcessorService = self._create_service(self.config.driver)

    def _create_service(self, driver: ImageProcessorDriver) -> ImageProcessorService:
        try:
            if driver not in ImageProcessorServiceRegistry:
                _load_driver_module(driver)
            return ImageProcessorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported image processor driver: {driver}")

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

def _load_driver_module(driver: ImageProcessorDriver) -> None:
    """Import the module that registers the given image processor driver.

    Convention: a driver "foo-bar" (ImageProcessorDriver.value) maps to
    mindor.core.component.services.image_processor.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_image_processor_service
    decorator, populating ImageProcessorServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.image_processor.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported image processor driver: {driver}") from e
