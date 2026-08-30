from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageDrawingComponentConfig, ImageDrawingDriver
from mindor.dsl.schema.action import ImageDrawingActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class ImageDrawingService(AsyncService):
    def __init__(self, id: str, config: ImageDrawingComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageDrawingComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageDrawingActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_drawing_service(driver: ImageDrawingDriver):
    def decorator(cls: Type[ImageDrawingService]) -> Type[ImageDrawingService]:
        ImageDrawingServiceRegistry[driver] = cls
        return cls
    return decorator

ImageDrawingServiceRegistry: Dict[ImageDrawingDriver, Type[ImageDrawingService]] = {}
