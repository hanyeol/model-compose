from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from mindor.dsl.schema.component import FileStoreComponentConfig, FileStoreDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import FileStoreService, FileStoreServiceRegistry
import importlib

@register_component(ComponentType.FILE_STORE)
class FileStoreComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: FileStoreComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: FileStoreService = self._create_service(self.config.driver)

    def _create_service(self, driver: FileStoreDriver) -> FileStoreService:
        try:
            if driver not in FileStoreServiceRegistry:
                _load_driver_module(driver)
            return FileStoreServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported file store driver: {driver}")

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

def _load_driver_module(driver: FileStoreDriver) -> None:
    """Import the module that registers the given file store driver.

    Convention: a driver "foo-bar" (FileStoreDriver.value) maps to
    mindor.core.component.services.file_store.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_file_store_service decorator,
    populating FileStoreServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.file_store.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported file store driver: {driver}") from e
