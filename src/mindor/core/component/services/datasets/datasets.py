from typing import Optional, List, Any
from mindor.dsl.schema.component import DatasetsComponentConfig, DatasetsDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import DatasetsService, DatasetsServiceRegistry
import importlib

@register_component(ComponentType.DATASETS)
class DatasetsComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: DatasetsComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: DatasetsService = self._create_service(self.config.driver)

    def _create_service(self, driver: DatasetsDriver) -> DatasetsService:
        try:
            if driver not in DatasetsServiceRegistry:
                self._load_driver_module(driver)
            return DatasetsServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported datasets driver: {driver}")

    def _load_driver_module(self, driver: DatasetsDriver) -> None:
        """Import the module that registers the given datasets driver.

        Convention: a driver "foo-bar" (DatasetsDriver.value) maps to
        mindor.core.component.services.datasets.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_datasets_service decorator,
        populating DatasetsServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.datasets.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported datasets driver: {driver}") from e

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
