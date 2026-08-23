from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioSynchronizerComponentConfig, AudioSynchronizerDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioSynchronizerService, AudioSynchronizerServiceRegistry
import importlib

@register_component(ComponentType.AUDIO_SYNCHRONIZER)
class AudioSynchronizerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioSynchronizerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: AudioSynchronizerService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioSynchronizerDriver) -> AudioSynchronizerService:
        try:
            if driver not in AudioSynchronizerServiceRegistry:
                self._load_driver_module(driver)
            return AudioSynchronizerServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio synchronizer driver: {driver}")

    def _load_driver_module(self, driver: AudioSynchronizerDriver) -> None:
        """Import the module that registers the given audio synchronizer driver.

        Convention: a driver "foo-bar" (AudioSynchronizerDriver.value) maps to
        mindor.core.component.services.audio_synchronizer.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_audio_synchronizer_service
        decorator, populating AudioSynchronizerServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_synchronizer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio synchronizer driver: {driver}") from e

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
