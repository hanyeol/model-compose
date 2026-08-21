from typing import Optional, List, Any
from mindor.dsl.schema.component import AudioAnalyzerComponentConfig, AudioAnalyzerDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioAnalyzerService, AudioAnalyzerServiceRegistry
import importlib

@register_component(ComponentType.AUDIO_ANALYZER)
class AudioAnalyzerComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioAnalyzerComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.service: AudioAnalyzerService = self._create_service(self.config.driver)

    def _create_service(self, driver: AudioAnalyzerDriver) -> AudioAnalyzerService:
        try:
            if driver not in AudioAnalyzerServiceRegistry:
                self._load_driver_module(driver)
            return AudioAnalyzerServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio analyzer driver: {driver}")

    def _load_driver_module(self, driver: AudioAnalyzerDriver) -> None:
        """Import the module that registers the given audio analyzer driver.

        Convention: a driver "foo-bar" (AudioAnalyzerDriver.value) maps to
        mindor.core.component.services.audio_analyzer.drivers.foo_bar —
        either a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_audio_analyzer_service
        decorator, populating AudioAnalyzerServiceRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_analyzer.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio analyzer driver: {driver}") from e

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
