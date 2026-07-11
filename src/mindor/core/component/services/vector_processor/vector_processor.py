from typing import Optional, List, Any
from mindor.dsl.schema.component import VectorProcessorComponentConfig, VectorProcessorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VectorProcessorService, VectorProcessorServiceRegistry
import importlib

@register_component(ComponentType.VECTOR_PROCESSOR)
class VectorProcessorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VectorProcessorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VectorProcessorService = self._create_service(self.config.driver)

    def _create_service(self, driver: VectorProcessorDriver) -> VectorProcessorService:
        try:
            if driver not in VectorProcessorServiceRegistry:
                _load_driver_module(driver)
            return VectorProcessorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported vector processor driver: {driver}")

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

def _load_driver_module(driver: VectorProcessorDriver) -> None:
    """Import the module that registers the given vector processor driver.

    Convention: a driver "foo-bar" (VectorProcessorDriver.value) maps to
    mindor.core.component.services.vector_processor.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_vector_processor_service
    decorator, populating VectorProcessorServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.vector_processor.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported vector processor driver: {driver}") from e
