from typing import Any
from mindor.dsl.schema.component import DataQueueComponentConfig, DataQueueDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import DataQueueDriver, DataQueueDriverRegistry
import importlib

@register_component(ComponentType.DATA_QUEUE)
class DataQueueComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: DataQueueComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: DataQueueDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: DataQueueDriverType) -> DataQueueDriver:
        try:
            if driver not in DataQueueDriverRegistry:
                self._load_backend_module(driver)
            return DataQueueDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported data queue driver: {driver}")

    def _load_backend_module(self, driver: DataQueueDriverType) -> None:
        """Import the module that registers the given data queue backend driver.

        Convention: a driver "foo-bar" (DataQueueDriverType.value) maps to
        mindor.core.component.services.data_queue.backends.foo_bar — either a
        single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_data_queue_driver decorator,
        populating DataQueueDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.data_queue.backends.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported data queue driver: {driver}") from e

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
