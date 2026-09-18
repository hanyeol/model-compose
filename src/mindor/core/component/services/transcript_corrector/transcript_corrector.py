from typing import Any
from mindor.dsl.schema.component import TranscriptCorrectorComponentConfig, TranscriptCorrectorDriverType
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import TranscriptCorrectorDriver, TranscriptCorrectorDriverRegistry
import importlib

@register_component(ComponentType.TRANSCRIPT_CORRECTOR)
class TranscriptCorrectorComponent(ComponentService):
    def __init__(
        self,
        id: str,
        config: TranscriptCorrectorComponentConfig,
        global_configs: ComponentGlobalConfigs,
        daemon: bool
    ):
        super().__init__(id, config, global_configs, daemon)

        self.driver: TranscriptCorrectorDriver = self._create_driver(self.config.driver)

    def _create_driver(self, driver: TranscriptCorrectorDriverType) -> TranscriptCorrectorDriver:
        try:
            if driver not in TranscriptCorrectorDriverRegistry:
                self._load_driver_module(driver)
            return TranscriptCorrectorDriverRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported transcript corrector driver: {driver}")

    def _load_driver_module(self, driver: TranscriptCorrectorDriverType) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.transcript_corrector.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported transcript corrector driver: {driver}") from e

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
