from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageProcessorComponentConfig, ImageProcessorDriverType
from mindor.dsl.schema.action import ImageProcessorActionConfig
from mindor.core.foundation.async_service import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ImageProcessorDriver(ComponentDriver):
    config: ImageProcessorComponentConfig

    async def run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_processor_driver(driver: ImageProcessorDriverType):
    def decorator(cls: Type[ImageProcessorDriver]) -> Type[ImageProcessorDriver]:
        ImageProcessorDriverRegistry[driver] = cls
        return cls
    return decorator

ImageProcessorDriverRegistry: Dict[ImageProcessorDriverType, Type[ImageProcessorDriver]] = {}
