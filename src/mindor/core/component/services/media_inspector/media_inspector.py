from typing import Optional, List, Any
from mindor.dsl.schema.component import MediaInspectorComponentConfig, MediaInspectorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import MediaInspectorService, MediaInspectorServiceRegistry
import importlib

@register_component(ComponentType.MEDIA_INSPECTOR)
class MediaInspectorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: MediaInspectorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: MediaInspectorService = self._create_service(self.config.driver)

    def _create_service(self, driver: MediaInspectorDriver) -> MediaInspectorService:
        try:
            if driver not in MediaInspectorServiceRegistry:
                self._load_driver_module(driver)
            return MediaInspectorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported media inspector driver: {driver}")

    def _load_driver_module(self, driver: MediaInspectorDriver) -> None:
        """Import the module that registers the given media inspector driver.

        Convention: a driver "foo-bar" (MediaInspectorDriver.value) maps to
        mindor.core.component.services.media_inspector.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_media_inspector_service
        decorator, populating MediaInspectorServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.media_inspector.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported media inspector driver: {driver}") from e

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
