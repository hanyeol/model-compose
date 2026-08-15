from typing import Type, Union, Literal, Optional, Dict, List, Tuple, Set, Annotated, Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioMixerComponentConfig, AudioMixerDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioMixerService, AudioMixerServiceRegistry
import importlib

@register_component(ComponentType.AUDIO_MIXER)
class AudioMixerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioMixerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: AudioMixerService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioMixerDriver) -> AudioMixerService:
        try:
            if driver not in AudioMixerServiceRegistry:
                self._load_driver_module(driver)
            return AudioMixerServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio mixer driver: {driver}")

    def _load_driver_module(self, driver: AudioMixerDriver) -> None:
        """Import the module that registers the given audio mixer driver.

        Convention: a driver "foo-bar" (AudioMixerDriver.value) maps to
        mindor.core.component.services.audio_mixer.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_audio_mixer_service
        decorator, populating AudioMixerServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_mixer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio mixer driver: {driver}") from e

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
