from typing import Optional, List, Any
from mindor.dsl.schema.component import TranscriptCorrectorComponentConfig, TranscriptCorrectorDriver
from mindor.dsl.schema.action import ActionConfig
from ...base import ComponentService, ComponentType, ComponentGlobalConfigs, register_component
from ...context import ComponentActionContext
from .base import TranscriptCorrectorService, TranscriptCorrectorServiceRegistry
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

        self.service: TranscriptCorrectorService = self._create_service(self.config.driver)

    def _create_service(self, driver: TranscriptCorrectorDriver) -> TranscriptCorrectorService:
        try:
            if driver not in TranscriptCorrectorServiceRegistry:
                self._load_driver_module(driver)
            return TranscriptCorrectorServiceRegistry[driver](self.id, self.config, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported transcript corrector driver: {driver}")

    def _load_driver_module(self, driver: TranscriptCorrectorDriver) -> None:
        driver_module = driver.value.replace("-", "_")

        try:
            importlib.import_module(f"mindor.core.component.services.transcript_corrector.drivers.{driver_module}")
        except ImportError as e:
            raise ValueError(f"Unsupported transcript corrector driver: {driver}") from e

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
