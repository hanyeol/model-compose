from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageAnalyzerComponentConfig, ImageAnalyzerDriver
from mindor.dsl.schema.action import ImageAnalyzerActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class ImageAnalyzerService(AsyncService):
    def __init__(self, id: str, config: ImageAnalyzerComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageAnalyzerComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageAnalyzerActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_analyzer_service(driver: ImageAnalyzerDriver):
    def decorator(cls: Type[ImageAnalyzerService]) -> Type[ImageAnalyzerService]:
        ImageAnalyzerServiceRegistry[driver] = cls
        return cls
    return decorator

ImageAnalyzerServiceRegistry: Dict[ImageAnalyzerDriver, Type[ImageAnalyzerService]] = {}
