from typing import Optional, List, Any
from mindor.dsl.schema.component import VideoCaptureComponentConfig, VideoCaptureDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import VideoCaptureService, VideoCaptureServiceRegistry
import importlib

@register_component(ComponentType.VIDEO_CAPTURE)
class VideoCaptureComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: VideoCaptureComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: VideoCaptureService = self._create_service(self.config.driver)

    def _create_service(self, driver: VideoCaptureDriver) -> VideoCaptureService:
        try:
            if driver not in VideoCaptureServiceRegistry:
                self._load_driver_module(driver)
            return VideoCaptureServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported video capture driver: {driver}")

    def _load_driver_module(self, driver: VideoCaptureDriver) -> None:
        """Import the module that registers the given video capture driver.

        Convention: a driver "foo-bar" (VideoCaptureDriver.value) maps to
        mindor.core.component.services.video_capture.drivers.foo_bar.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.video_capture.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported video capture driver: {driver}") from e

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
