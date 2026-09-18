from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import RtmpPublisherComponentConfig, RtmpPublisherDriverType
from mindor.dsl.schema.action import RtmpPublisherActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class RtmpPublisherDriver(ComponentDriver):
    def __init__(self, id: str, config: RtmpPublisherComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: RtmpPublisherComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: RtmpPublisherActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_rtmp_publisher_driver(driver: RtmpPublisherDriverType):
    def decorator(cls: Type[RtmpPublisherDriver]) -> Type[RtmpPublisherDriver]:
        RtmpPublisherDriverRegistry[driver] = cls
        return cls
    return decorator

RtmpPublisherDriverRegistry: Dict[RtmpPublisherDriverType, Type[RtmpPublisherDriver]] = {}
