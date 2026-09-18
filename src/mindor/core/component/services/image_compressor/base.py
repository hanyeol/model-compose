from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageCompressorComponentConfig, ImageCompressorDriverType
from mindor.dsl.schema.action import ImageCompressorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ImageCompressorDriver(ComponentDriver):
    def __init__(self, id: str, config: ImageCompressorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageCompressorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_compressor_driver(driver: ImageCompressorDriverType):
    def decorator(cls: Type[ImageCompressorDriver]) -> Type[ImageCompressorDriver]:
        ImageCompressorDriverRegistry[driver] = cls
        return cls
    return decorator

ImageCompressorDriverRegistry: Dict[ImageCompressorDriverType, Type[ImageCompressorDriver]] = {}
