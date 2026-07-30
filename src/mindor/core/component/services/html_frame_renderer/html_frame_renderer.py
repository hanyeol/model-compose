from typing import Any
from mindor.dsl.schema.component import HtmlFrameRendererComponentConfig, HtmlFrameRendererDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import HtmlFrameRendererService, HtmlFrameRendererServiceRegistry
import importlib

@register_component(ComponentType.HTML_FRAME_RENDERER)
class HtmlFrameRendererComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: HtmlFrameRendererComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool,
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: HtmlFrameRendererService = self._create_service(self.config.driver)

    def _create_service(self, driver: HtmlFrameRendererDriver) -> HtmlFrameRendererService:
        try:
            if driver not in HtmlFrameRendererServiceRegistry:
                self._load_driver_module(driver)
            return HtmlFrameRendererServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported html_frame_renderer driver: {driver}")

    def _load_driver_module(self, driver: HtmlFrameRendererDriver) -> None:
        """Import the module that registers the given html_frame_renderer driver.

        Convention: a driver "foo-bar" (HtmlFrameRendererDriver.value) maps to
        mindor.core.component.services.html_frame_renderer.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_html_frame_renderer_service
        decorator, populating HtmlFrameRendererServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(
                f"mindor.core.component.services.html_frame_renderer.drivers.{driver_module}"
            )
        except ImportError as e:
            raise ValueError(f"Unsupported html_frame_renderer driver: {driver}") from e

    async def _start(self) -> None:
        await self.service.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.service.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.service.run(action, context)
