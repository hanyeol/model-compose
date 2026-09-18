from typing import Any
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioPlaybackDriver, AudioPlaybackDriverRegistry
import importlib

@register_component(ComponentType.AUDIO_PLAYBACK)
class AudioPlaybackComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioPlaybackComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: AudioPlaybackDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: AudioPlaybackDriverType) -> AudioPlaybackDriver:
        try:
            if driver not in AudioPlaybackDriverRegistry:
                self._load_driver_module(driver)
            return AudioPlaybackDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio playback driver: {driver}")

    def _load_driver_module(self, driver: AudioPlaybackDriverType) -> None:
        """Import the module that registers the given audio playback driver.

        Convention: a driver "foo-bar" (AudioPlaybackDriverType.value) maps to
        mindor.core.component.services.audio_playback.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_audio_playback_driver
        decorator, populating AudioPlaybackDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_playback.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio playback driver: {driver}") from e

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
