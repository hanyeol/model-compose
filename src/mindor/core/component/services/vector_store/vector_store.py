from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import VectorStoreComponentConfig, VectorStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VectorStoreService, VectorStoreServiceRegistry
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

        self.service: VectorStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: VectorStoreDriver) -> VectorStoreService:
        try:
            if driver not in VectorStoreServiceRegistry:
                _load_driver_module(driver)
            return VectorStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported vector store driver: {driver}")

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

def _load_driver_module(driver: VectorStoreDriver) -> None:
    """Import the module that registers the given vector store driver.

    Convention: a driver "foo-bar" (VectorStoreDriver.value) maps to
    mindor.core.component.services.vector_store.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_vector_store_service
    decorator, populating VectorStoreServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.vector_store.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported vector store driver: {driver}") from e
