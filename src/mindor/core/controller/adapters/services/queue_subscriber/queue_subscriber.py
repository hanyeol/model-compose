from __future__ import annotations
from typing import TYPE_CHECKING

from typing import List
from mindor.dsl.schema.controller import QueueSubscriberControllerAdapterConfig, QueueSubscriberDriverType, ControllerAdapterType
from ...base import ControllerAdapterService, register_controller_adapter
from .base import CommonQueueSubscriberControllerAdapterService, QueueSubscriberControllerAdapterDriverRegistry

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

@register_controller_adapter(ControllerAdapterType.QUEUE_SUBSCRIBER)
class QueueSubscriberControllerAdapterService(ControllerAdapterService):
    def __init__(
        self,
        config: QueueSubscriberControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool
    ):
        super().__init__(config, controller, daemon)

        self.driver: CommonQueueSubscriberControllerAdapterService = self._create_driver(config.driver)

    def get_declared_requirements(self) -> List[str]:
        requirements = list(self._get_setup_requirements() or [])
        requirements.extend(self.driver.get_declared_requirements())

        return requirements

    def _create_driver(self, driver: QueueSubscriberDriverType) -> CommonQueueSubscriberControllerAdapterService:
        if not QueueSubscriberControllerAdapterDriverRegistry:
            from . import drivers
        try:
            return QueueSubscriberControllerAdapterDriverRegistry[driver](self.config, self.controller, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported queue subscriber driver: {driver}")

    async def _serve(self) -> None:
        await self.driver.start()
        await self.driver.wait_until_stopped()

    async def _shutdown(self) -> None:
        await self.driver.stop()
