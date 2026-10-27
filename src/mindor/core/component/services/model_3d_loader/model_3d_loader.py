from typing import Any
from mindor.dsl.schema.component import Model3DLoaderComponentConfig, Model3DLoaderDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import Model3DLoaderDriver, Model3DLoaderDriverRegistry
import importlib

@register_component(ComponentType.MODEL_3D_LOADER)
class Model3DLoaderComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: Model3DLoaderComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: Model3DLoaderDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: Model3DLoaderDriverType) -> Model3DLoaderDriver:
        try:
            if driver not in Model3DLoaderDriverRegistry:
                self._load_driver_module(driver)
            return Model3DLoaderDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported 3D model loader driver: {driver}")

    def _load_driver_module(self, driver: Model3DLoaderDriverType) -> None:
        """Import the driver module so its @register_model_3d_loader_driver decorator fires."""
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.model_3d_loader.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported 3D model loader driver: {driver}") from e

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
