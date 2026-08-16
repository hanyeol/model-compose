from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageCompressorComponentConfig, ImageCompressorDriver
from mindor.dsl.schema.action import ImageCompressorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext

class ImageCompressorService(AsyncService):
    def __init__(self, id: str, config: ImageCompressorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageCompressorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        return await self._run(action, context)

    @abstractmethod
    async def _run(self, action: ImageCompressorActionConfig, context: ComponentActionContext) -> Any:
        pass

def register_image_compressor_service(driver: ImageCompressorDriver):
    def decorator(cls: Type[ImageCompressorService]) -> Type[ImageCompressorService]:
        ImageCompressorServiceRegistry[driver] = cls
        return cls
    return decorator

ImageCompressorServiceRegistry: Dict[ImageCompressorDriver, Type[ImageCompressorService]] = {}
