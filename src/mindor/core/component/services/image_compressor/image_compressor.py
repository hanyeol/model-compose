from typing import Optional, List, Any
from mindor.dsl.schema.component import ImageCompressorComponentConfig, ImageCompressorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import ImageCompressorService, ImageCompressorServiceRegistry
import importlib

@register_component(ComponentType.IMAGE_COMPRESSOR)
class ImageCompressorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: ImageCompressorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: ImageCompressorService = self._create_service(self.config.driver)

    def _create_service(self, driver: ImageCompressorDriver) -> ImageCompressorService:
        try:
            if driver not in ImageCompressorServiceRegistry:
                self._load_driver_module(driver)
            return ImageCompressorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported image compressor driver: {driver}")

    def _load_driver_module(self, driver: ImageCompressorDriver) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.image_compressor.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported image compressor driver: {driver}") from e

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
