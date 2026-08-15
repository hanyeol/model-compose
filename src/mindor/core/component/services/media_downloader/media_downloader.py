from typing import Optional, List, Any
from mindor.dsl.schema.component import MediaDownloaderComponentConfig, MediaDownloaderDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import MediaDownloaderService, MediaDownloaderServiceRegistry
import importlib

@register_component(ComponentType.MEDIA_DOWNLOADER)
class MediaDownloaderComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: MediaDownloaderComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: MediaDownloaderService = self._create_service(self.config.driver)

    def _create_service(self, driver: MediaDownloaderDriver) -> MediaDownloaderService:
        try:
            if driver not in MediaDownloaderServiceRegistry:
                self._load_driver_module(driver)
            return MediaDownloaderServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported media downloader driver: {driver}")

    def _load_driver_module(self, driver: MediaDownloaderDriver) -> None:
        """Import the module that registers the given media downloader driver.

        Convention: a driver "foo-bar" (MediaDownloaderDriver.value) maps to
        mindor.core.component.services.media_downloader.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_media_downloader_service
        decorator, populating MediaDownloaderServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.media_downloader.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported media downloader driver: {driver}") from e

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
