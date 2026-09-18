from __future__ import annotations
from typing import TYPE_CHECKING

from typing import Type, Dict, Optional, Any
from mindor.dsl.schema.controller import QueueSubscriberDriverType
from mindor.dsl.schema.controller.adapter.impl.queue_subscriber.impl.common import CommonQueueSubscriberControllerAdapterConfig
from mindor.core.foundation import AsyncService

if TYPE_CHECKING:
    from mindor.core.controller.base import ControllerService

class CommonQueueSubscriberControllerAdapterService(AsyncService):
    def __init__(
        self,
        config: CommonQueueSubscriberControllerAdapterConfig,
        controller: ControllerService,
        daemon: bool
    ):
        super().__init__(daemon)

        self.config = config
        self.controller = controller

def register_queue_subscriber_controller_adapter_driver(driver: QueueSubscriberDriverType):
    def decorator(cls: Type[CommonQueueSubscriberControllerAdapterService]) -> Type[CommonQueueSubscriberControllerAdapterService]:
        QueueSubscriberControllerAdapterDriverRegistry[driver] = cls
        return cls
    return decorator

QueueSubscriberControllerAdapterDriverRegistry: Dict[QueueSubscriberDriverType, Type[CommonQueueSubscriberControllerAdapterService]] = {}
