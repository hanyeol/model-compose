from typing import Optional, List, Any
from mindor.dsl.schema.component import DataQueueComponentConfig, DataQueueDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import DataQueueService, DataQueueServiceRegistry
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

        self.service: DataQueueService = self._create_service(self.config.driver)

    def _create_service(self, driver: DataQueueDriver) -> DataQueueService:
        try:
            if driver not in DataQueueServiceRegistry:
                _load_backend_module(driver)
            return DataQueueServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported data queue driver: {driver}")

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

def _load_backend_module(driver: DataQueueDriver) -> None:
    """Import the module that registers the given data queue backend driver.

    Convention: a driver "foo-bar" (DataQueueDriver.value) maps to
    mindor.core.component.services.data_queue.backends.foo_bar — either a
    single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_data_queue_service decorator,
    populating DataQueueServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.data_queue.backends.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported data queue driver: {driver}") from e
