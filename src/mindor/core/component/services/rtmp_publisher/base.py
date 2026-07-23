from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriver
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class RtmpPublisherService(AsyncService):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: RtmpPublisherComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_rtmp_publisher_service(driver: RtmpPublisherDriver):
    def decorator(cls: Type[RtmpPublisherService]) -> Type[RtmpPublisherService]:
        RtmpPublisherServiceRegistry[driver] = cls
        return cls
    return decorator

RtmpPublisherServiceRegistry: Dict[RtmpPublisherDriver, Type[RtmpPublisherService]] = {}
