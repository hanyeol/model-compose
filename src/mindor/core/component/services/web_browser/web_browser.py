from typing import Any
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import WebBrowserService, WebBrowserServiceRegistry
import importlib

@register_component(ComponentType.WEB_BROWSER)
class WebBrowserComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: WebBrowserComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: WebBrowserService = self._create_service(self.config.driver)

    def _create_service(self, driver: WebBrowserDriver) -> WebBrowserService:
        try:
            if driver not in WebBrowserServiceRegistry:
                self._load_driver_module(driver)
            return WebBrowserServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported web browser driver: {driver}")

    def _load_driver_module(self, driver: WebBrowserDriver) -> None:
        """Import the module that registers the given web browser driver.

        Convention: a driver "foo-bar" (WebBrowserDriver.value) maps to
        mindor.core.component.services.web_browser.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_web_browser_service decorator,
        populating WebBrowserServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.web_browser.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported web browser driver: {driver}") from e

    async def _start(self) -> None:
        await self.service.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
