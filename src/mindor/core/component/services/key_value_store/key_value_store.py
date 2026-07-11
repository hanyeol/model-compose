from typing import Optional, List, Any
from mindor.dsl.schema.component import KeyValueStoreComponentConfig, KeyValueStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import KeyValueStoreService, KeyValueStoreServiceRegistry
import importlib

@register_component(ComponentType.KEY_VALUE_STORE)
class KeyValueStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: KeyValueStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: KeyValueStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: KeyValueStoreDriver) -> KeyValueStoreService:
        try:
            if driver not in KeyValueStoreServiceRegistry:
                _load_driver_module(driver)
            return KeyValueStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported key-value store driver: {driver}")

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

def _load_driver_module(driver: KeyValueStoreDriver) -> None:
    """Import the module that registers the given key-value store driver.

    Convention: a driver "foo-bar" (KeyValueStoreDriver.value) maps to
    mindor.core.component.services.key_value_store.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_kv_store_service decorator,
    populating KeyValueStoreServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.key_value_store.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported key-value store driver: {driver}") from e
