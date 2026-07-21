from typing import Optional, List, Any
from mindor.dsl.schema.component import SentenceSplitterComponentConfig, SentenceSplitterDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import SentenceSplitterService, SentenceSplitterServiceRegistry
import importlib

@register_component(ComponentType.SENTENCE_SPLITTER)
class SentenceSplitterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: SentenceSplitterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: SentenceSplitterService = self._create_service(self.config.driver)

    def _create_service(self, driver: SentenceSplitterDriver) -> SentenceSplitterService:
        try:
            if driver not in SentenceSplitterServiceRegistry:
                _load_driver_module(driver)
            return SentenceSplitterServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported sentence splitter driver: {driver}")

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

def _load_driver_module(driver: SentenceSplitterDriver) -> None:
    """Import the module that registers the given sentence splitter driver.

    Convention: a driver "foo-bar" (SentenceSplitterDriver.value) maps to
    mindor.core.component.services.sentence_splitter.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_sentence_splitter_service
    decorator, populating SentenceSplitterServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.sentence_splitter.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported sentence splitter driver: {driver}") from e
