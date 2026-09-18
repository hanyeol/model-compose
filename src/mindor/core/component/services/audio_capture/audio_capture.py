from typing import Any
from mindor.dsl.schema.component import AudioCaptureComponentConfig, AudioCaptureDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioCaptureDriver, AudioCaptureDriverRegistry
import importlib

@register_component(ComponentType.AUDIO_CAPTURE)
class AudioCaptureComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioCaptureComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: AudioCaptureDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: AudioCaptureDriverType) -> AudioCaptureDriver:
        try:
            if driver not in AudioCaptureDriverRegistry:
                self._load_driver_module(driver)
            return AudioCaptureDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio capture driver: {driver}")

    def _load_driver_module(self, driver: AudioCaptureDriverType) -> None:
        """Import the module that registers the given audio capture driver.

        Convention: a driver "foo-bar" (AudioCaptureDriverType.value) maps to
        mindor.core.component.services.audio_capture.drivers.foo_bar.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_capture.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio capture driver: {driver}") from e

    async def _setup(self) -> None:
        await self.driver.setup()

    async def _teardown(self) -> None:
        await self.driver.teardown()

    async def _start(self) -> None:
        await self.driver.start()

        await super()._start()

    async def _stop(self) -> None:
        await super()._stop()

        await self.driver.stop()

    async def _run(self, action: ActionConfig, context: ComponentActionContext) -> Any:
        return await self.driver.run(action, context)
