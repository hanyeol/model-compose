from typing import Type, Optional, Dict, List, Any
from abc import abstractmethod
from mindor.dsl.schema.component import ImageProcessorComponentConfig, ImageProcessorDriver
from mindor.dsl.schema.action import ImageProcessorActionConfig
from mindor.core.foundation import AsyncService
from ...context import ComponentActionContext
import asyncio

class ImageProcessorService(AsyncService):
    def __init__(self, id: str, config: ImageProcessorComponentConfig, daemon: bool):
        super().__init__(daemon)

        self.id: str = id
        self.config: ImageProcessorComponentConfig = config

    def get_setup_requirements(self) -> Optional[List[str]]:
        return None

    async def run(self, action: ImageProcessorActionConfig, context: ComponentActionContext) -> Any:
        return await self.run_in_thread(self._run, action, context, asyncio.get_running_loop())

    @abstractmethod
    async def _run(self, action: ImageProcessorActionConfig, context: ComponentActionContext, loop: asyncio.AbstractEventLoop) -> Any:
        pass

def register_image_processor_service(driver: ImageProcessorDriver):
    def decorator(cls: Type[ImageProcessorService]) -> Type[ImageProcessorService]:
        ImageProcessorServiceRegistry[driver] = cls
        return cls
    return decorator

ImageProcessorServiceRegistry: Dict[ImageProcessorDriver, Type[ImageProcessorService]] = {}
