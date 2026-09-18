from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriverType
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from mindor.core.component.base import ComponentDriver
from ...context import ComponentActionContext

class ImageAnalyzerDriver(ComponentDriver):
    def __init__(self, id: str, config: ImageAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageAnalyzerComponentConfig = config

    def _get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_analyzer_driver(driver: ImageAnalyzerDriverType):
    def decorator(cls: Type[ImageAnalyzerDriver]) -> Type[ImageAnalyzerDriver]:
        ImageAnalyzerDriverRegistry[driver] = cls
        return cls
    return decorator

ImageAnalyzerDriverRegistry: Dict[ImageAnalyzerDriverType, Type[ImageAnalyzerDriver]] = {}
