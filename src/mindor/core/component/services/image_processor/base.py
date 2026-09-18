from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageProcessorComponentConfig, ImageProcessorDriverType
from mindor.dsl.schema.action import ImageProcessorActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ImageProcessorDriver(ComponentDriver):
    def __init__(self, id: str, config: ImageProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageProcessorComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

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
