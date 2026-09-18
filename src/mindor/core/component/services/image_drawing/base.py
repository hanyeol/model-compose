from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageDrawingComponentConfig, ImageDrawingDriverType
from mindor.dsl.schema.action import ImageDrawingActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ImageDrawingDriver(ComponentDriver):
    def __init__(self, id: str, config: ImageDrawingComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageDrawingComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_drawing_driver(driver: ImageDrawingDriverType):
    def decorator(cls: Type[ImageDrawingDriver]) -> Type[ImageDrawingDriver]:
        ImageDrawingDriverRegistry[driver] = cls
        return cls
    return decorator

ImageDrawingDriverRegistry: Dict[ImageDrawingDriverType, Type[ImageDrawingDriver]] = {}
