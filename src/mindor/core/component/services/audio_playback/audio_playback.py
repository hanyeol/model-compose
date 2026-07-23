from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioPlaybackComponentConfig, AudioPlaybackDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioPlaybackService, AudioPlaybackServiceRegistry
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

        self.service: AudioPlaybackService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioPlaybackDriver) -> AudioPlaybackService:
        try:
            if driver not in AudioPlaybackServiceRegistry:
                _load_driver_module(driver)
            return AudioPlaybackServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio playback driver: {driver}")

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

def _load_driver_module(driver: AudioPlaybackDriver) -> None:
    """Import the module that registers the given audio playback driver.

    Convention: a driver "foo-bar" (AudioPlaybackDriver.value) maps to
    mindor.core.component.services.audio_playback.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_audio_playback_service
    decorator, populating AudioPlaybackServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.audio_playback.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported audio playback driver: {driver}") from e
