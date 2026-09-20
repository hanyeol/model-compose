from typing import Any
from mindor.dsl.schema.component import Model3DConverterComponentConfig, Model3DConverterDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import Model3DConverterDriver, Model3DConverterDriverRegistry
import importlib

@register_component(ComponentType.MODEL_3D_CONVERTER)
class Model3DConverterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: Model3DConverterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: Model3DConverterDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: Model3DConverterDriverType) -> Model3DConverterDriver:
        try:
            if driver not in Model3DConverterDriverRegistry:
                self._load_driver_module(driver)
            return Model3DConverterDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported 3D model converter driver: {driver}")

    def _load_driver_module(self, driver: Model3DConverterDriverType) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.model_3d_converter.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported 3D model converter driver: {driver}") from e

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
