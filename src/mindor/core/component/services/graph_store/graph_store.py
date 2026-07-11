from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import GraphStoreComponentConfig, GraphStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import GraphStoreService, GraphStoreServiceRegistry
import importlib

@register_component(ComponentType.GRAPH_STORE)
class GraphStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: GraphStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: GraphStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: GraphStoreDriver) -> GraphStoreService:
        try:
            if driver not in GraphStoreServiceRegistry:
                _load_driver_module(driver)
            return GraphStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported graph store driver: {driver}")

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

def _load_driver_module(driver: GraphStoreDriver) -> None:
    """Import the module that registers the given graph store driver.

    Convention: a driver "foo-bar" (GraphStoreDriver.value) maps to
    mindor.core.component.services.graph_store.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_graph_store_service decorator,
    populating GraphStoreServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.graph_store.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported graph store driver: {driver}") from e
