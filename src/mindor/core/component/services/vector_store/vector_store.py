from typing import Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VectorStoreComponentConfig, VectorStoreDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VectorStoreDriver, VectorStoreDriverRegistry
import importlib

@register_component(ComponentType.VECTOR_STORE)
class VectorStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VectorStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: VectorStoreDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: VectorStoreDriverType) -> VectorStoreDriver:
        try:
            if driver not in VectorStoreDriverRegistry:
                self._load_driver_module(driver)
            return VectorStoreDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported vector store driver: {driver}")

    def _load_driver_module(self, driver: VectorStoreDriverType) -> None:
        """Import the module that registers the given vector store driver.

        Convention: a driver "foo-bar" (VectorStoreDriverType.value) maps to
        mindor.core.component.services.vector_store.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_vector_store_driver
        decorator, populating VectorStoreDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.vector_store.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported vector store driver: {driver}") from e

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
