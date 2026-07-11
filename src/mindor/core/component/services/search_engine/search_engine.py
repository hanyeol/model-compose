from typing import Optional, List, Any
from mindor.dsl.schema.component import SearchEngineComponentConfig, SearchEngineDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import SearchEngineService, SearchEngineServiceRegistry
import importlib

@register_component(ComponentType.SEARCH_ENGINE)
class SearchEngineComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: SearchEngineComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: SearchEngineService = self._create_service(self.config.driver)

    def _create_service(self, driver: SearchEngineDriver) -> SearchEngineService:
        try:
            if driver not in SearchEngineServiceRegistry:
                _load_driver_module(driver)
            return SearchEngineServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported search engine driver: {driver}")

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

def _load_driver_module(driver: SearchEngineDriver) -> None:
    """Import the module that registers the given search engine driver.

    Convention: a driver "foo-bar" (SearchEngineDriver.value) maps to
    mindor.core.component.services.search_engine.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_search_engine_service
    decorator, populating SearchEngineServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.search_engine.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported search engine driver: {driver}") from e
