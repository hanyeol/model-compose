from __future__ import annotations
from typing import TYPE_CHECKING

from mindor.dsl.schema.controller import QueueSubscriberControllerAdapterConfig, QueueSubscriberDriver, ControllerAdapterType
from ...base import ControllerAdapterService, register_controller_adapter
from .base import CommonQueueSubscriberControllerAdapterService, QueueSubscriberControllerAdapterServiceRegistry

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
        self.service: CommonQueueSubscriberControllerAdapterService = self._create_service(config.driver)

    def _create_service(self, driver: QueueSubscriberDriver) -> CommonQueueSubscriberControllerAdapterService:
        if not QueueSubscriberControllerAdapterServiceRegistry:
            from . import drivers
        try:
            return QueueSubscriberControllerAdapterServiceRegistry[driver](self.config, self.controller, self.daemon)
        except KeyError:
            raise ValueError(f"Unsupported queue subscriber driver: {driver}")

    async def _serve(self) -> None:
        await self.service.start()
        await self.service.wait_until_stopped()

    async def _shutdown(self) -> None:
        await self.service.stop()
