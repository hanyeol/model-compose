from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioConverterComponentConfig, AudioConverterDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioConverterService, AudioConverterServiceRegistry
import importlib

@register_component(ComponentType.AUDIO_CONVERTER)
class AudioConverterComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioConverterComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: AudioConverterService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioConverterDriver) -> AudioConverterService:
        try:
            if driver not in AudioConverterServiceRegistry:
                _load_driver_module(driver)
            return AudioConverterServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio converter driver: {driver}")

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

def _load_driver_module(driver: AudioConverterDriver) -> None:
    """Import the module that registers the given audio converter driver.

    Convention: a driver "foo-bar" (AudioConverterDriver.value) maps to
    mindor.core.component.services.audio_converter.drivers.foo_bar — either
    a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
    Importing the module triggers its @register_audio_converter_service
    decorator, populating AudioConverterServiceRegistry.
    """
    driver_module = driver.value.replace("-", "_")

    try:
        importlib.import_module(f"mindor.core.component.services.audio_converter.drivers.{driver_module}")
    except ImportError as e:
        raise ValueError(f"Unsupported audio converter driver: {driver}") from e
