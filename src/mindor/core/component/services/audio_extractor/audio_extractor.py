from typing import Any
from collections.abc import AsyncIterator
from mindor.dsl.schema.component import AudioExtractorComponentConfig, AudioExtractorDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import AudioExtractorDriver, AudioExtractorDriverRegistry
import importlib

@register_component(ComponentType.AUDIO_EXTRACTOR)
class AudioExtractorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: AudioExtractorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: AudioExtractorDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: AudioExtractorDriverType) -> AudioExtractorDriver:
        try:
            if driver not in AudioExtractorDriverRegistry:
                self._load_driver_module(driver)
            return AudioExtractorDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported audio extractor driver: {driver}")

    def _load_driver_module(self, driver: AudioExtractorDriverType) -> None:
        """Import the module that registers the given audio extractor driver.

        Convention: a driver "foo-bar" (AudioExtractorDriverType.value) maps to
        mindor.core.component.services.audio_extractor.drivers.foo_bar — either
        a single-file module (foo_bar.py) or a package (foo_bar/__init__.py).
        Importing the module triggers its @register_audio_extractor_driver
        decorator, populating AudioExtractorDriverRegistry.
        """
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.audio_extractor.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported audio extractor driver: {driver}") from e

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
