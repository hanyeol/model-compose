from typing import Any
from mindor.dsl.schema.component import WebBrowserComponentConfig, WebBrowserDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import WebBrowserDriver, WebBrowserDriverRegistry
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

        self.driver: WebBrowserDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: WebBrowserDriverType) -> WebBrowserDriver:
        try:
            if driver not in WebBrowserDriverRegistry:
                self._load_driver_module(driver)
            return WebBrowserDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported web browser driver: {driver}")

    def _load_driver_module(self, driver: WebBrowserDriverType) -> None:
        """Import the module that registers the given web browser driver.

        Convention: a driver "foo-bar" (WebBrowserDriverType.value) maps to
        mindor.core.component.services.web_browser.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_web_browser_driver decorator,
        populating WebBrowserDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.web_browser.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported web browser driver: {driver}") from e

    async def _start(self) -> None:
        await self.driver.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.driver.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.driver.run(action, context)
