from typing import Optional, List, Any
from mindor.dsl.schema.component import SubtitleLoaderComponentConfig, SubtitleLoaderDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import SubtitleLoaderService, SubtitleLoaderServiceRegistry
import importlib

@register_component(ComponentType.SUBTITLE_LOADER)
class SubtitleLoaderComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: SubtitleLoaderComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: SubtitleLoaderService = self._create_service(self.config.driver)

    def _create_service(self, driver: SubtitleLoaderDriver) -> SubtitleLoaderService:
        try:
            if driver not in SubtitleLoaderServiceRegistry:
                self._load_driver_module(driver)
            return SubtitleLoaderServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported subtitle loader driver: {driver}")

    def _load_driver_module(self, driver: SubtitleLoaderDriver) -> None:
        """Import the module that registers the given subtitle loader driver.

        Convention: a driver "foo-bar" (SubtitleLoaderDriver.value) maps to
        mindor.core.component.services.subtitle_loader.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_subtitle_loader_service
        decorator, populating SubtitleLoaderServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.subtitle_loader.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported subtitle loader driver: {driver}") from e

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
